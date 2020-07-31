import os
import sys


basedir = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(basedir, '..', '..')))
sys.path.append(os.path.abspath(os.path.join(basedir, '..', '..', 'src', 'modules', 'feature-extractor')))
sys.path.append(os.path.abspath(os.path.join(basedir, '..', '..', 'src', 'modules', 'region-classifier')))
sys.path.append(os.path.abspath(os.path.join(basedir, '..', '..', 'src', 'modules', 'region-refiner')))

from feature_extractor import FeatureExtractor
#import region_classifier
#import region_refiner
from shutil import copyfile
## Experiment configuration
feature_extractor = FeatureExtractor('configs/config_feature_task_federico.yaml', 'configs/config_target_task_FALKON_federico_icwt_21.yaml')#'configs/config_target_task_FALKON_federico.yaml')
"""
## Retrieve feature extractor (either by loading it or by training it)
try:
    feature_extractor.loadFeatureExtractor()
except OSError:
    print('Feature extractor will be trained from scratch.')
    feature_extractor.trainFeatureExtractor()
"""
"""
## Extract features for the train/val/test sets
lambdas = [0.0000001, 0.000001, 0.00001, 0.0001, 0.001, 0.01]
#lambdas = [0.01, 0.1, 1, 10, 100, 1000]
sigmas = [10, 15, 20, 25, 30, 50, 100, 1, 5, 1000, 10000]
for lam in lambdas:
    for sigma in sigmas:
        print('---------------------------------------- Computing average recall with lambda %s and sigma %s ----------------------------------------' %(str(lam), str(sigma)))
        copyfile('cv_regressors_falkon_m30000_train_with_test_set/cv_lambda%s_sigma%s' %(str(lam).replace(".","_"), str(sigma).replace(".","_")), 'cv_reg30000')
        feature_extractor.extractFeatures()
"""
"""
#lambdas = [0.0000000001, 0.000000001, 0.00000001, 0.0000001, 0.000001, 0.00001, 0.0001, 0.001, 0.01, 0.1, 1, 10, 100, 1000, 10000, 100000, 1000000, 10000000]
lambdas = [0.000001, 0.00001, 0.0001, 0.001, 0.01, 0.1, 1, 10, 100, 1000, 10000, 100000, 1000000, 10000000]
for lam in lambdas:
    print('---------------------------------------- Computing average recall with lambda %s ----------------------------------------' %(str(lam)))
    copyfile('cv_regressors_linear_icwt_21/cv_lambda%s' %(str(lam).replace(".","_")), 'cv_reg_lin')
    #copyfile('cv_regressors_linear_icwt_21' %(str(lam).replace(".","_")), 'cv_reg_lin')
    feature_extractor.extractFeatures()
"""
feature_extractor.extractFeatures()

## Train region refiner

## Start the cross validation

### - Set parameters
### - Train region classifier
### - Test region classifier (on validation set)
### - Test region refiner (on validation set)
### - Save/store results

## Test the best model (on the test set)
