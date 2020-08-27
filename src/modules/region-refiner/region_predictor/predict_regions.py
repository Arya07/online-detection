import numpy as np
import os
import torch

basedir = os.path.dirname(__file__)

class RegionPredictor():
    def __init__(self, cfg, models=None, boxes=None):
        self.cfg = cfg
        self.features_format = self.cfg['FEATURE_INFO']['FORMAT']
        self.normalize_features = False
        self.feat = None
        self.boxes = boxes
        self.stats = None
        self.models = models

    def __call__(self):
        pred_boxes = self.predict()
        return pred_boxes

    def predict(self):
        chosen_classes = self.cfg['CHOSEN_CLASSES']

        num_clss = len(chosen_classes)

        img_size = self.boxes[0].size
        img_width = img_size[0]
        img_height = img_size[1]

        # Loop on the list of boxlists
        for i in range(len(self.boxes)):
            if self.feat is None:
                print('Features not passed, returning')
                return
            else:
                # Exclude ground-truth boxes
                I = np.nonzero(self.feat[i]['gt'] == 0)
                feat = torch.tensor(self.feat[i]['feat'][I, :][0], device='cuda')

            # Normalize features
            if self.normalize_features:
                feat = feat - self.stats['mean']
                feat = feat * (20 / self.stats['mean_norm'].item())

            ex_box = self.boxes[i].bbox.to('cuda')
            num_boxes = ex_box.size()[0]
            # Initialize refined boxes with example boxes in the 0-th dimension
            refined_boxes = ex_box
            for j in range(1, len(chosen_classes)):
                weights = self.models[j-1]['Beta']['0']['weights'].view(1,-1)
                for k in range(1, 4):
                    weights = torch.cat((weights, self.models[j-1]['Beta'][str(k)]['weights'].view(1,-1)))
                weights = torch.t(weights)
                Y = torch.matmul(feat, weights[:-1])
                Y += weights[-1]
                Y = torch.matmul(Y, self.models[j-1]['T_inv'])
                Y += self.models[j-1]['mu']

                dst_ctr_x = Y[:,0]
                dst_ctr_y = Y[:,1]
                dst_scl_x = Y[:,2]
                dst_scl_y = Y[:,3]
    
                src_w = ex_box[:,2] - ex_box[:,0] + np.spacing(1)
                src_h = ex_box[:,3] - ex_box[:,1] + np.spacing(1)
                src_ctr_x = ex_box[:,0] + 0.5 * src_w
                src_ctr_y = ex_box[:,1] + 0.5 * src_h
                pred_ctr_x = (dst_ctr_x * src_w) + src_ctr_x
                pred_ctr_y = (dst_ctr_y * src_h) + src_ctr_y
                pred_w = torch.exp(dst_scl_x) * src_w
                pred_h = torch.exp(dst_scl_y) * src_h
                pred_boxes = torch.cat(((pred_ctr_x - 0.5 * pred_w).view(num_boxes,1), (pred_ctr_y - 0.5 * pred_h).view(num_boxes,1)), dim=1)
                pred_boxes = torch.cat((pred_boxes, (pred_ctr_x + 0.5 * pred_w).view(num_boxes,1)),dim=1)
                pred_boxes = torch.cat((pred_boxes, (pred_ctr_y + 0.5 * pred_h).view(num_boxes,1)),dim=1)


                if '.pkl' in self.features_format:
                    pred_boxes[:, 0] = torch.max(pred_boxes[:, 0], torch.zeros(pred_boxes[:,0].size(), device='cuda'))
                    pred_boxes[:, 1] = torch.max(pred_boxes[:, 1], torch.zeros(pred_boxes[:,1].size(), device='cuda'))
                    pred_boxes[:, 2] = torch.min(pred_boxes[:, 2], torch.full(pred_boxes[:,2].size(), img_width - 1, device='cuda'))
                    pred_boxes[:, 3] = torch.min(pred_boxes[:, 3], torch.full(pred_boxes[:,3].size(), img_height - 1, device='cuda'))
                elif '.mat' in self.features_format:
                    pred_boxes[:, 0] = torch.max(pred_boxes[:, 0], torch.ones(pred_boxes[:,0].size(), device='cuda'))
                    pred_boxes[:, 1] = torch.max(pred_boxes[:, 1], torch.ones(pred_boxes[:,1].size(), device='cuda'))
                    pred_boxes[:, 2] = torch.min(pred_boxes[:, 2], torch.full(pred_boxes[:,2].size(), img_width, device='cuda'))
                    pred_boxes[:, 3] = torch.min(pred_boxes[:, 3], torch.full(pred_boxes[:,3].size(), img_height, device='cuda'))
                # Concatenate box predictions for each class
                refined_boxes = torch.cat((refined_boxes, pred_boxes), dim=1)

            
            refined_boxes = refined_boxes.view((num_boxes, len(chosen_classes), 4))

            self.boxes[i].bbox = refined_boxes

        return self.boxes
