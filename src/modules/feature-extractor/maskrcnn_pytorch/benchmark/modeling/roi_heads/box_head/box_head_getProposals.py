# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved.
import torch
from torch import nn

from .roi_box_feature_extractors import make_roi_box_feature_extractor
from .roi_box_predictors import make_roi_box_predictor
from .inference import make_roi_box_post_processor
from .loss import make_roi_box_loss_evaluator

import os
import numpy as np

import time

from maskrcnn_pytorch.benchmark.utils.evaluations import compute_overlap_torch
import math

class ROIBoxHead(torch.nn.Module):
    """
    Generic Box Head class.
    """

    def __init__(self, cfg, in_channels):
        super(ROIBoxHead, self).__init__()
        self.feature_extractor = make_roi_box_feature_extractor(cfg, in_channels)
        self.predictor = make_roi_box_predictor(
            cfg, self.feature_extractor.out_channels)
        self.post_processor = make_roi_box_post_processor(cfg)
        self.loss_evaluator = make_roi_box_loss_evaluator(cfg)
        self.output_dir = cfg.OUTPUT_DIR
        self.cfg = cfg

        self.num_classes = self.cfg.MINIBOOTSTRAP.DETECTOR.NUM_CLASSES
        self.iterations = self.cfg.MINIBOOTSTRAP.DETECTOR.ITERATIONS
        self.batch_size = self.cfg.MINIBOOTSTRAP.DETECTOR.BATCH_SIZE
        self.negatives = []
        self.positives = []
        self.current_batch = []
        self.current_batch_size = []
        for i in range(self.num_classes):
            self.negatives.append([])
            self.current_batch.append(0)
            self.current_batch_size.append(0)
            self.positives.append(torch.empty((0, 2048), device='cuda'))    # TODO parametrize
            for j in range(self.iterations):
                self.negatives[i].append(torch.empty((0, 2048), device='cuda'))  # TODO parametrize
        self.negatives_to_pick = self.cfg.MINIBOOTSTRAP.DETECTOR.NEGATIVES_PER_BATCH
        self.still_to_complete = list(range(self.num_classes))

        # Regressor reatures
        self.X = torch.empty((0, 2048), dtype=torch.float32, device='cuda')
        # Regressor target values
        self.Y = torch.empty((0, 4), dtype=torch.float32, device='cuda')
        # Regressor overlap amounts
        self.O = None
        # Regressor classes
        self.C = torch.empty((0), dtype=torch.float32, device='cuda')

        self.test_boxes = []

    def forward(self, features, proposals, image_name_path, targets=None, gt_bbox = None, gt_label = None, img_size= None,start_time = None, num_classes = 30, gt_labels_list=None, is_train = True):
        if is_train:
            return self.forward_train(features, proposals, image_name_path, targets=targets, gt_bbox = gt_bbox, gt_label = gt_label, img_size= img_size,start_time = start_time, num_classes = num_classes, gt_labels_list=gt_labels_list)
        else:
            return self.forward_test(features, proposals, image_name_path, targets=targets, gt_bbox = gt_bbox, gt_label = gt_label, img_size= img_size,start_time = start_time, num_classes = num_classes, gt_labels_list=gt_labels_list)

    def forward_train(self, features, proposals, image_name_path, targets=None, gt_bbox = None, gt_label = None, img_size= None,start_time = None, num_classes = 30, gt_labels_list=None):

        # Extract features that will be fed to the final classifier.
        x = self.feature_extractor(features, proposals)
        proposals[0] = proposals[0].resize((img_size[0], img_size[1]))
        gt_bbox = gt_bbox.resize((img_size[0], img_size[1]))

        # Compute proposed bboxes and gt bboxes
        arr_proposals = proposals[0].bbox
        arr_gt_bbox = gt_bbox.bbox
        if self.cfg.FEATURES_FORMAT == '.mat':
            # Add 1 to every coordinate as Matlab is 1-based
            arr_proposals = arr_proposals + 1
            arr_proposals[:, 2] = torch.clamp(arr_proposals[:, 2], 1, img_size[0])
            arr_proposals[:, 0] = torch.clamp(arr_proposals[:, 0], 1, img_size[0])
            arr_proposals[:, 3] = torch.clamp(arr_proposals[:, 3], 1, img_size[1])
            arr_proposals[:, 1] = torch.clamp(arr_proposals[:, 1], 1, img_size[1])

            arr_gt_bbox = arr_gt_bbox + 1
            arr_gt_bbox[:, 2] = torch.clamp(arr_gt_bbox[:, 2], 1, img_size[0])
            arr_gt_bbox[:, 0] = torch.clamp(arr_gt_bbox[:, 0], 1, img_size[0])
            arr_gt_bbox[:, 3] = torch.clamp(arr_gt_bbox[:, 3], 1, img_size[1])
            arr_gt_bbox[:, 1] = torch.clamp(arr_gt_bbox[:, 1], 1, img_size[1])
        else:

            arr_proposals[:, 2] = torch.clamp(arr_proposals[:, 2], 1, img_size[0]-1)
            arr_proposals[:, 0] = torch.clamp(arr_proposals[:, 0], 1, img_size[0]-1)
            arr_proposals[:, 3] = torch.clamp(arr_proposals[:, 3], 1, img_size[1]-1)
            arr_proposals[:, 1] = torch.clamp(arr_proposals[:, 1], 1, img_size[1]-1)

            arr_gt_bbox[:, 2] = torch.clamp(arr_gt_bbox[:, 2], 1, img_size[0]-1)
            arr_gt_bbox[:, 0] = torch.clamp(arr_gt_bbox[:, 0], 1, img_size[0]-1)
            arr_gt_bbox[:, 3] = torch.clamp(arr_gt_bbox[:, 3], 1, img_size[1]-1)
            arr_gt_bbox[:, 1] = torch.clamp(arr_gt_bbox[:, 1], 1, img_size[1]-1)


        # Count gt bboxes
        if gt_label is not None:
            len_gt = gt_label.size()[0]
        else:
            len_gt = 0
        # Count num of proposals
        num_proposals = arr_proposals.size()[0]- len_gt
        # Specify the classes of the ground truth boxes, then set the classes of the not-gt proposals to 0
        if gt_label is not None:
            arr_class = torch.cat((gt_label, torch.zeros((num_proposals, 1), device='cuda', dtype=torch.uint8)), dim=0)
        else:
            arr_class = torch.zeros((num_proposals,1), device='cuda')
        # Initialize overlaps with gts to 0
        overlap = torch.zeros((arr_proposals.size()[0], num_classes), dtype=torch.float, device='cuda')
        # Compute max overlap of each proposal with each class
        for j in range(arr_gt_bbox.size()[0]):
            overlap[:, gt_labels_list[j]-1] = torch.max(overlap[:, gt_labels_list[j]-1], compute_overlap_torch(arr_gt_bbox[j], arr_proposals))

        # Loop on all the gt boxes
        for i in range(len(gt_labels_list)):
            # Concatenate each gt to the positive tensor for its corresponding class
            self.positives[gt_labels_list[i]-1] = torch.cat((self.positives[gt_labels_list[i]-1], x[i].view(-1, 2048)))

            # Extract regressor positives, i.e. with overlap > 0.6
            pos_ids = overlap[:,gt_labels_list[i]-1] > 0.6
            regr_positives_i = x[pos_ids].view(-1, 2048)
            # Add class and features to C and X
            self.C = torch.cat((self.C, torch.full((torch.sum(pos_ids), 1), gt_labels_list[i], device='cuda')))
            self.X = torch.cat((self.X, regr_positives_i))

            # Compute targets
            ex_boxes = arr_proposals[pos_ids].view(-1, 4)
            gt_boxes = torch.ones(ex_boxes.size(), device='cuda') * arr_proposals[i].view(-1, 4)

            src_w = ex_boxes[:,2] - ex_boxes[:,0]
            src_h = ex_boxes[:,3] - ex_boxes[:,1]
            src_ctr_x = ex_boxes[:,0] + 0.5 * src_w
            src_ctr_y = ex_boxes[:,1] + 0.5 * src_h

            gt_w = gt_boxes[:,2] - gt_boxes[:,0]
            gt_h = gt_boxes[:,3] - gt_boxes[:,1]
            gt_ctr_x = gt_boxes[:,0] + 0.5 * gt_w
            gt_ctr_y = gt_boxes[:,1] + 0.5 * gt_h

            dst_ctr_x = (gt_ctr_x - src_ctr_x) / src_w
            dst_ctr_y = (gt_ctr_y - src_ctr_y) / src_h
            dst_scl_w = torch.log(gt_w / src_w)
            dst_scl_h = torch.log(gt_h / src_h)

            target = torch.stack((dst_ctr_x, dst_ctr_y, dst_scl_w, dst_scl_h), dim=1)
            self.Y = torch.cat((self.Y, target), dim=0)

        # Fill batches for minibootstrap
        indices_to_remove = []
        # Loop on all the classes that doesn't have full batches
        for i in self.still_to_complete:
            # Add random negatives, if there isn't a gt corresponding to that class
            if i+1 not in gt_labels_list:
                neg_i = x[torch.randint(x.size()[0], (self.negatives_to_pick,))].view(-1, 2048)
            # Add random examples with iou < 0.3 otherwise
            else:
                neg_i = x[overlap[:,i] < 0.3].view(-1, 2048)
                neg_i = neg_i[torch.randint(neg_i.size()[0], (self.negatives_to_pick,))].view(-1, 2048)
            # Add negatives splitting them into batches
            neg_to_add = math.ceil(self.negatives_to_pick/self.iterations)
            ind_to_add = 0
            for b in range(self.current_batch[i], self.iterations):
                if self.negatives[i][b].size()[0] >= self.batch_size:
                    self.current_batch[i] += 1
                    if self.current_batch[i] >= self.iterations:
                        indices_to_remove.append(i)
                    continue
                else:
                    end_interval = int(ind_to_add + min(neg_to_add, self.batch_size - self.negatives[i][b].size()[0], self.negatives_to_pick - ind_to_add))
                    self.negatives[i][b] = torch.cat((self.negatives[i][b], neg_i[ind_to_add:end_interval].view(-1, 2048)))
                    ind_to_add = end_interval
                    if ind_to_add == self.negatives_to_pick:
                        break
        for index in indices_to_remove:
            self.still_to_complete.remove(index)

        
        return None, None, None


    def forward_test(self, features, proposals, image_name_path, targets=None, gt_bbox = None, gt_label = None, img_size= None,start_time = None, num_classes = 30, gt_labels_list=None):

        # Extract features that will be fed to the final classifier.
        x = self.feature_extractor(features, proposals)
        proposals[0] = proposals[0].resize((img_size[0], img_size[1]))
        gt_bbox = gt_bbox.resize((img_size[0], img_size[1]))
        
        # Compute proposed bboxes and gt bboxes
        arr_proposals = proposals[0].bbox
        arr_gt_bbox = gt_bbox.bbox
        if self.cfg.FEATURES_FORMAT == '.mat':
            # Add 1 to every coordinate as Matlab is 1-based
            arr_proposals = arr_proposals + 1
            arr_proposals[:, 2] = torch.clamp(arr_proposals[:, 2], 1, img_size[0])
            arr_proposals[:, 0] = torch.clamp(arr_proposals[:, 0], 1, img_size[0])
            arr_proposals[:, 3] = torch.clamp(arr_proposals[:, 3], 1, img_size[1])
            arr_proposals[:, 1] = torch.clamp(arr_proposals[:, 1], 1, img_size[1])

            arr_gt_bbox = arr_gt_bbox + 1
            arr_gt_bbox[:, 2] = torch.clamp(arr_gt_bbox[:, 2], 1, img_size[0])
            arr_gt_bbox[:, 0] = torch.clamp(arr_gt_bbox[:, 0], 1, img_size[0])
            arr_gt_bbox[:, 3] = torch.clamp(arr_gt_bbox[:, 3], 1, img_size[1])
            arr_gt_bbox[:, 1] = torch.clamp(arr_gt_bbox[:, 1], 1, img_size[1])
        else:
            arr_proposals[:, 2] = torch.clamp(arr_proposals[:, 2], 1, img_size[0]-1)
            arr_proposals[:, 0] = torch.clamp(arr_proposals[:, 0], 1, img_size[0]-1)
            arr_proposals[:, 3] = torch.clamp(arr_proposals[:, 3], 1, img_size[1]-1)
            arr_proposals[:, 1] = torch.clamp(arr_proposals[:, 1], 1, img_size[1]-1)

            arr_gt_bbox[:, 2] = torch.clamp(arr_gt_bbox[:, 2], 1, img_size[0]-1)
            arr_gt_bbox[:, 0] = torch.clamp(arr_gt_bbox[:, 0], 1, img_size[0]-1)
            arr_gt_bbox[:, 3] = torch.clamp(arr_gt_bbox[:, 3], 1, img_size[1]-1)
            arr_gt_bbox[:, 1] = torch.clamp(arr_gt_bbox[:, 1], 1, img_size[1]-1)

        # Count gt bboxes
        if gt_label is not None:
            len_gt = gt_label.size()[0]
        else:
            len_gt = 0
        # Count num of proposals
        num_proposals = arr_proposals.size()[0]- len_gt
        # Specify the classes of the ground truth boxes, then set the classes of the not-gt proposals to 0
        if gt_label is not None:
            arr_class = torch.cat((gt_label, torch.zeros((num_proposals, 1), device='cuda', dtype=torch.uint8)), dim=0)
        else:
            arr_class = torch.zeros((num_proposals,1), device='cuda')
        # Signal if the box is a gt or not
        arr_gt = arr_class > 0

        self.test_boxes.append({'boxes': arr_proposals.cpu().numpy(), 'feat': x.cpu().numpy(), 'gt': arr_gt.cpu().numpy()})

        return None, None, None



def build_roi_box_head(cfg, in_channels):
    """
    Constructs a new box head.
    By default, uses ROIBoxHead, but if it turns out not to be enough, just register a new class
    and make it a parameter in the config
    """
    return ROIBoxHead(cfg, in_channels)
