export const ROLES=['admin','analyst','viewer'];
export const STATES=['queued','running','completed','failed'];
export const STATE_LABELS={queued:'等待计算',running:'计算进行中',completed:'已完成',failed:'失败需修复'};
export const SEQ_STATUSES=['running','frozen','exhausted'];
export const SEQ_STATUS_LABELS={running:'进行中',frozen:'结论已冻结',exhausted:'登记对已用完·未达线'};
export const OUTCOMES=['concordant','discordant','tie'];
export const OUTCOME_LABELS={concordant:'同向',discordant:'反向',tie:'并列跳过'};
