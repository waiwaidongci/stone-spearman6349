"""序贯双向符号检验：混合似然比 e 值，任意时点查看保持整轮双侧误报率 ≤ α。

每对独立试件比较孔隙率与吸水率的增减方向：
同向记 s、反向记 d；任一指标并列则该对整对跳过（不贡献证据）。

对非并列对，把“同向概率” p 用均匀先验 Beta(1,1) 混合，得到 e 值

    E_n = ∫₀¹ 2ⁿ pˢ(1-p)ᵈ dp = 2ⁿ · s!·d! / (n+1)!，   n = s + d

在“同向与反向等可能（p=1/2）、各对独立”的原假设下，E_n 是非负鞅且
E[E_n | 过去] = E_{n-1}（因为 ∫₀¹ 2p dp = 1），故 E[E_n] = 1。由 Ville 不等式

    P(任意时点存在 n 使 E_n ≥ 1/α) ≤ α

即无论中途查看多少次、在哪个时点停下，整轮双侧误报率都不超过 α。
达到 E_n ≥ 1/α 即冻结结论；冻结前已用测值全部保留在证据明细中。
"""
import math
from src.config.domain import DOMAIN

PRIOR_LABEL = '均匀先验 Beta(1,1)'
MAX_E_VALUE = 1e300
LOG_MAX_E = math.log(MAX_E_VALUE)

FIELD_A, FIELD_B = DOMAIN['fields'][0][0], DOMAIN['fields'][1][0]


def threshold(alpha):
    return 1.0 / float(alpha)


def log_threshold(alpha):
    return -math.log(float(alpha))


def direction_outcome(values_a, values_b):
    """返回 concordant / discordant / tie。任一指标并列即 tie（整对跳过）。"""
    da = float(values_a[FIELD_A]) - float(values_b[FIELD_A])
    db = float(values_a[FIELD_B]) - float(values_b[FIELD_B])
    if da == 0 or db == 0:
        return 'tie'
    return 'concordant' if (da > 0) == (db > 0) else 'discordant'


def log_e_value(concordant, discordant):
    s, d = int(concordant), int(discordant)
    n = s + d
    return n * math.log(2.0) + math.lgamma(s + 1) + math.lgamma(d + 1) - math.lgamma(n + 2)


def e_value(concordant, discordant):
    return safe_exp(log_e_value(concordant, discordant))


def safe_exp(x):
    if x > LOG_MAX_E:
        return MAX_E_VALUE
    if x < -745.0:
        return 0.0
    return math.exp(x)


def crossed(concordant, discordant, alpha):
    return log_e_value(concordant, discordant) >= log_threshold(alpha)
