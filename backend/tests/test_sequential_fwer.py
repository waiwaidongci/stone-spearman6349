import os,sys,math
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
import numpy as np
import pytest
from src.services.sequential_algorithm import log_e_value,log_threshold,e_value,direction_outcome

def anytime_false_positive_rate(theta,alpha=0.05,trials=4000,max_pairs=250,seed=7):
    """模拟任意时点查看下的误报：首对起任意时刻 E_n ≥ 1/α 即算误报。"""
    rng=np.random.default_rng(seed)
    threshold=log_threshold(alpha)
    hits=0
    for _ in range(trials):
        s=d=0;hit=False
        for n in range(1,max_pairs+1):
            if rng.random()<theta: s+=1
            else: d+=1
            if log_e_value(s,d)>=threshold: hit=True;break
        hits+=hit
    return hits/trials

def test_anytime_type_one_error_under_null_is_within_alpha():
    rate=anytime_false_positive_rate(0.5,trials=3000)
    # Ville 保证理论上 ≤ 5%；有限样本允许轻微波动。
    assert rate<=0.06,rate

def test_balanced_near_null_still_controlled():
    rate=anytime_false_positive_rate(0.52,trials=3000)
    assert rate<=0.10,rate

def test_directional_alternatives_are_detected():
    # 同向概率 0.8 时绝大多数轮次会在 250 对内达线
    rate=anytime_false_positive_rate(0.8,trials=600,max_pairs=250,seed=11)
    assert rate>=0.95,rate

def test_e_value_is_nonnegative_martingale_expectation_at_first_step():
    # 单步下 E[E_1] = (E(1,0)+E(0,1))/2 = 1，验证混合构造正确
    assert abs((e_value(1,0)+e_value(0,1))/2-1.0)<1e-12
