import os
import sys
import torch


basedir = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(basedir, '..', '..')))
sys.path.append(os.path.abspath(os.path.join(basedir, '..', '..', 'src', 'modules', 'feature-extractor')))
sys.path.append(os.path.abspath(os.path.join(basedir, '..', '..', 'src', 'modules', 'region-classifier')))
sys.path.append(os.path.abspath(os.path.join(basedir, '..', '..', 'src', 'modules', 'region-refiner')))

from feature_extractor import FeatureExtractor
#import region_classifier
#from region_refiner import RegionRefiner

## Experiment configuration
feature_extractor = FeatureExtractor('configs/config_feature_task_federico.yaml', 'configs/config_target_task_FALKON_federico.yaml', 'configs/config_rpn_federico_icwt_21.yaml') #'configs/config_rpn_federico.yaml') #

## Retrieve feature extractor (either by loading it or by training it)
try:
    feature_extractor.loadFeatureExtractor()
except OSError:
    print('Feature extractor will be trained from scratch.')
    #feature_extractor.trainFeatureExtractor()

feature_extractor.extractRPNFeatures()
quit()
"""
## Extract features for the train/val/test sets
#feature_extractor.extractFeatures()

## Experiment configuration
#feature_extractor = FeatureExtractor('configs/config_feature_task.yaml', 'configs/config_target_task_FALKON.yaml')
region_refiner = RegionRefiner('configs/config_region_refiner_server_RPN.yaml')

## Retrieve feature extractor (either by loading it or by training it)
#try:
#    feature_extractor.loadFeatureExtractor()
#except OSError:
#    print('Feature extractor will be trained from scratch.')
#    feature_extractor.trainFeatureExtractor()

## Extract features for the train/val/test sets
#feature_extractor.extractFeatures()

## Train region refiner
regressors = region_refiner.trainRegionRefiner()
torch.save(regressors, 'regressors_RPN')
## Start the cross validation
#quit()


## Train region refiner

## Start the cross validation

### - Set parameters
### - Train region classifier
### - Test region classifier (on validation set)
### - Test region refiner (on validation set)
### - Save/store results

## Test the best model (on the test set)
"""
