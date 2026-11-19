import math,os,sys
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from src.services.sequential_algorithm import log_e_value,e_value,direction_outcome,safe_exp

def brute_log_e(s,d):
    # ∫₀¹ 2^n p^s (1-p)^d dp = 2^n · s! d! / (n+1)!
    n=s+d
    return n*math.log(2)+math.lgamma(s+1)+math.lgamma(d+1)-math.lgamma(n+2)

def numeric_log_e(s,d,steps=200000):
    import numpy as np
    p=(np.arange(steps)+0.5)/steps
    return float(np.log(np.trapezoid(2.0**(s+d)*p**s*(1-p)**d,p))) if hasattr(np,'trapezoid') else float(np.log(np.trapz(2.0**(s+d)*p**s*(1-p)**d,p)))

def test_matches_factorial_formula():
    for s in range(0,12):
        for d in range(0,12):
            assert abs(log_e_value(s,d)-brute_log_e(s,d))<1e-9

def test_matches_numeric_integral_small():
    for s,d in ((0,0),(1,0),(3,2),(7,4),(10,6)):
        assert abs(log_e_value(s,d)-numeric_log_e(s,d))<1e-3

def test_null_expectation_is_one_for_single_step():
    import numpy as np
    # E over one pair under p=1/2 of E_1 = (E(concordant)+E(discordant))/2 = 1
    vals=[]
    for s,d in ((1,0),(0,1)):
        vals.append(e_value(s,d))
    assert abs(sum(vals)/2-1.0)<1e-12

def test_growth_reverse_and_ties():
    assert e_value(10,0)>e_value(9,0)
    assert e_value(8,0)>e_value(3,0)
    assert abs(e_value(1,0)-1.0)<1e-12
    assert safe_exp(1e9)==1e300 and safe_exp(-1e9)==0.0

def test_outcome_classification():
    a={'porosity':5,'absorption':2};b={'porosity':4,'absorption':1}
    assert direction_outcome(a,b)=='concordant'
    assert direction_outcome(b,a)=='concordant'
    assert direction_outcome({'porosity':5,'absorption':1},{'porosity':4,'absorption':2})=='discordant'
    assert direction_outcome({'porosity':5,'absorption':2},{'porosity':5,'absorption':1})=='tie'
    assert direction_outcome({'porosity':5,'absorption':2},{'porosity':4,'absorption':2})=='tie'
