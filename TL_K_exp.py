#!/usr/bin/env python
# encoding: utf-8
# This file tries to do semi-supervised learning on target domain test data
# using all data [source_train, source_test, source_para, target_train, target_test, target_para].
# We do not complete `K`.
# The solution for prediction `f` is exact.
# The tuning parameters `w_2` for coefficient for regularization term. (we use default gamme, which is the sqrt of dimension for each domain)

import sys
import numpy as np
from sklearn.datasets import load_svmlight_file
from sklearn.metrics import average_precision_score
from sklearn.metrics import roc_auc_score
from sklearn.metrics import label_ranking_average_precision_score
from sklearn.metrics import label_ranking_loss
from dataclass import DataClass
from sklearn.preprocessing import normalize
from sklearn.preprocessing import scale
from solve import solve_and_eval
import scipy.sparse as sp
import cvxopt
from cvxopt import matrix
np.random.seed(123)


def eigen_decompose(K, offset, max_k=128):
    W_s = K[:offset[2], :offset[2]]
    W_t = K[offset[2]:, offset[2]:]
    v_s, Q_s = sp.linalg.eigsh(W_s, k=max_k)
    v_t, Q_t = sp.linalg.eigsh(W_t, k=max_k)
    return v_s, Q_s, v_t, Q_t

def get_K_exp(K_exp, offset, v_s, Q_s, v_t, Q_t, beta, kernel_normal):
    Y_st = K_exp[:offset[2], offset[2]:]
    Lambda_s = np.diag(np.exp(beta*v_s))
    Lambda_t = np.diag(np.exp(beta*v_t))
    K_ss = Q_s.dot(Lambda_s.dot(Q_s.T))
    K_tt = Q_t.dot(Lambda_t.dot(Q_t.T))
    K_st = K_ss.dot(Y_st.dot(K_tt))
    if not kernel_normal:
        K_st = normalize(K_st)
    K_exp[:offset[2], offset[2]:] = K_st
    K_exp[offset[2]:, :offset[2]] = K_st.T
    return K_exp

# grid search hyperparameter on valid set
# bList: beta for exp kernel
# wList: weight for Manifold regularization term
# pList: sparsity for kernel (p-nearest neighbor)
# kernel_type: 'rbf' or 'cosine'
# source_data_type: 'full' or 'normal'
# kernel_normal: whether to normalized the W or not
# zero_diag_flag: whether zero out the diagonal or not
def grid(kernel_type='cosine', zero_diag_flag=True, kernel_normal=False, bList=None, wList=None, pList=None):
    dc = DataClass(valid_flag=True, kernel_normal=kernel_normal)
    dc.kernel_type = kernel_type
    dc.zero_diag_flag = zero_diag_flag
    y, I, K, offset = dc.get_TL_Kernel()

    # run eigen decomposition on K
    v_s, Q_s, v_t, Q_t = eigen_decompose(K, offset, max_k=128)

    best_b = -1
    best_w = -1
    best_p = -1
    best_auc = -1
    for log2_b in bList:
        beta = 2**log2_b
        K_exp = K.copy()
        K_exp = get_K_exp(K_exp, offset, v_s, Q_s, v_t, Q_t, beta, kernel_normal)
        for log2_w in wList:
            for log2_p in pList:
                if log2_p == -1:
                    K_sp = K_exp
                else:
                    K_sp = DataClass.sym_sparsify_K(K_exp, 2**log2_p)
                auc, ap, rl = solve_and_eval(y, I, K_sp, offset, 2**log2_w)
                print('log2_b %3d log2_w %3d log2_p %3d auc %8f ap %6f rl %6f' %(log2_b, log2_w, log2_p, auc, ap, rl))
                if best_auc < auc:
                    best_b = log2_b
                    best_w = log2_w
                    best_p = log2_p
                return
    print('best parameters: log2_b %3d log2_w %3d log2_p %3d auc %6f' \
            % (best_b, best_w, best_p, best_auc))

def run_testset(kernel_type='cosine', zero_diag_flag=True, kernel_normal=False, log2_b=None, log2_w=None, log2_p=None):
    dc = DataClass(valid_flag=False, kernel_normal=kernel_normal)
    dc.kernel_type = kernel_type
    dc.zero_diag_flag = zero_diag_flag
    # dc.source_data_type = 'parallel' # CorrNet test
    y, I, K, offset = dc.get_TL_Kernel()

    # run eigen decomposition on K
    v_s, Q_s, v_t, Q_t = eigen_decompose(K, offset, max_k=128)
    # v_s, Q_s, v_t, Q_t = eigen_decompose(K, offset, max_k=5)

    beta = 2**log2_b
    K_exp = K.copy()
    K_exp = get_K_exp(K_exp, offset, v_s, Q_s, v_t, Q_t, beta, kernel_normal)

    if log2_p == -1:
        K_sp = K_exp
    else:
        K_sp = DataClass.sym_sparsify_K(K_exp, 2**log2_p)

    auc, ap, rl = solve_and_eval(y, I, K_sp, offset, 2**log2_w)
    print('test set: auc %6f ap %6f rl %6f' % (auc, ap, rl))


if __name__ == '__main__':
    bList = np.arange(-20, -8, 2)
    wList = np.arange(-12, -10, 2)
    pList = np.arange(-1, 11, 2)
    #grid(kernel_type='cosine', zero_diag_flag=True, kernel_normal=False, bList=bList, wList=wList, pList=pList)
    run_testset(kernel_type='cosine', zero_diag_flag=True, kernel_normal=False, log2_b=-12, log2_w=-12, log2_p=-1)
