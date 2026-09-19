import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { settlementApi } from '../../api/settlements.js';
import DataTable from '../../components/DataTable.jsx';
import DetailList from '../../components/DetailList.jsx';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import { GradeTag, ScorePill, SeverityTag, StatusTag } from '../../components/Tags.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { formatDateTime, formatDate, formatMoney } from '../../utils/format.js';

const TABS = [
  { key: 'deductions', label: '扣款构成' },
  { key: 'inspections', label: '巡查明细' },
  { key: 'issues', label: '问题整改明细' },
];

export default function SettlementDetailPage() {
  const { settlementId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [tab, setTab] = useState('deductions');
  const [action, setAction] = useState(null);

  const { data: settlement, loading, error, reload } = useAsync(
    () => settlementApi.detail(settlementId),
    [settlementId],
  );
  const { data: options } = useAsync(() => settlementApi.transitions(settlementId), [settlementId]);

  const remove = async () => {
    if (!window.confirm(`确认删除结算单 ${settlement?.code}？`)) return;
    try {
      await settlementApi.remove(settlementId);
      toast.success('已删除');
      navigate('/settlements');
    } catch (err) {
      toast.error(err.message);
    }
  };

  const assessed = settlement?.status !== '待考核';

  return (
    <>
      <PageHeader
        title={settlement ? `${settlement.code} · ${settlement.period_month}` : '结算单详情'}
        description={
          settlement
            ? `${settlement.vendor?.name} · ${settlement.contract?.name ?? ''}`
            : '加载中…'
        }
        actions={
          <>
            <Link className="btn" to="/settlements">
              返回台账
            </Link>
            <Link className="btn" to={`/contracts/${settlement?.contract_id}`}>
              合同详情
            </Link>
            {settlement?.status !== '已结算' ? (
              <button type="button" className="btn btn-danger" onClick={remove}>
                删除
              </button>
            ) : null}
          </>
        }
      />
      <div className="content">
        {error ? <div className="alert alert-error">{error.message}</div> : null}
        {loading && !settlement ? <div className="loading-block">加载中…</div> : null}

        {settlement ? (
          <>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="label">月度合同费用</div>
                <div className="value" style={{ fontSize: 26 }}>
                  ¥{formatMoney(settlement.monthly_fee)}
                </div>
                <div className="foot">
                  {formatDate(settlement.period_start)} ~ {formatDate(settlement.period_end)}
                </div>
              </div>
              <div className={`stat-card${settlement.total_deduction > 0 ? ' is-warning' : ''}`}>
                <div className="label">考核扣款合计</div>
                <div className="value" style={{ fontSize: 26 }}>
                  ¥{formatMoney(settlement.total_deduction)}
                </div>
                <div className="foot">
                  质量 ¥{formatMoney(settlement.quality_deduction)} · 问题 ¥
                  {formatMoney(settlement.issue_deduction)} · 超期 ¥
                  {formatMoney(settlement.overdue_deduction)}
                  {settlement.manual_deduction ? (
                    <> · 其他 ¥{formatMoney(settlement.manual_deduction)}</>
                  ) : null}
                </div>
              </div>
              <div className="stat-card is-info">
                <div className="label">本月应结算金额</div>
                <div className="value" style={{ fontSize: 26 }}>
                  {assessed ? `¥${formatMoney(settlement.payable_amount)}` : '待考核'}
                </div>
                <div className="foot">月度费用 − 考核扣款合计</div>
              </div>
              <div className="stat-card">
                <div className="label">考核状态</div>
                <div className="value" style={{ fontSize: 22 }}>
                  <StatusTag status={settlement.status} />
                </div>
                <div className="foot">
                  考核：{settlement.assessed_by || '-'}
                  {settlement.assessed_at ? ` · ${formatDateTime(settlement.assessed_at)}` : ''}
                </div>
              </div>
            </div>

            <section className="card">
              <div className="card-title">
                <h3>考核操作</h3>
                <span className="hint">
                  已结算后金额锁定；撤销结算或退回重做后可重新按当期数据考核
                </span>
              </div>
              <div className="action-group">
                {settlement.status === '待考核' ? (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => setAction({ kind: 'assess' })}
                  >
                    执行月度考核（按巡查与问题数据计算扣款）
                  </button>
                ) : null}
                {settlement.status === '已考核' ? (
                  <>
                    <button type="button" className="btn" onClick={() => setAction({ kind: 'assess' })}>
                      重新考核
                    </button>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => setAction({ kind: 'manual' })}
                    >
                      登记其他扣款调整
                    </button>
                  </>
                ) : null}
                {(options || []).map((option) => (
                  <button
                    key={option.status}
                    type="button"
                    className={`btn${option.status === '已结算' ? ' btn-primary' : ''}`}
                    onClick={() => setAction({ kind: 'transition', option })}
                  >
                    {option.action}
                  </button>
                ))}
              </div>
              <DetailList
                items={[
                  {
                    label: '考核指标',
                    value: `巡查 ${settlement.inspection_count} 次 · 均分 ${
                      settlement.avg_score != null ? settlement.avg_score : '无'
                    } · 当期新增问题 ${settlement.issue_count} 条 · 超期未闭环 ${settlement.overdue_count} 条`,
                  },
                  {
                    label: '结算信息',
                    value: settlement.settled_at
                      ? `${settlement.settled_by} 于 ${formatDateTime(settlement.settled_at)} 确认结算`
                      : '尚未确认结算',
                  },
                  {
                    label: '其他调整',
                    value: settlement.manual_deduction
                      ? `¥${formatMoney(settlement.manual_deduction)}（${settlement.manual_reason}）`
                      : '无',
                  },
                  { label: '备注', value: settlement.remark || '无' },
                ]}
              />
            </section>

            <div className="inline">
              {TABS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`btn btn-sm${tab === item.key ? ' btn-primary' : ''}`}
                  onClick={() => setTab(item.key)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {tab === 'deductions' ? (
              <section className="card">
                <div className="card-title">
                  <h3>扣款构成</h3>
                  <span className="hint">考核时固化快照，作为结算金额的计算依据</span>
                </div>
                {!assessed ? (
                  <div className="empty-block">该结算单尚未考核，执行考核后生成扣款明细。</div>
                ) : settlement.details.length ? (
                  <DataTable
                    rows={settlement.details}
                    columns={[
                      {
                        key: 'type',
                        title: '扣款类型',
                        render: (row) => (
                          <StatusTag
                            status={
                              { quality: '质量考核', issue: '问题整改', overdue: '超期未闭环', manual: '其他调整' }[
                                row.type
                              ] || row.type
                            }
                          />
                        ),
                      },
                      { key: 'name', title: '扣款项目', wrap: true },
                      {
                        key: 'amount',
                        title: '金额（元）',
                        render: (row) => (
                          <span className={row.amount < 0 ? 'money-positive' : 'money-negative'}>
                            {row.amount < 0 ? '+' : '-'}¥{formatMoney(Math.abs(row.amount))}
                          </span>
                        ),
                      },
                      { key: 'basis', title: '计算依据', wrap: true },
                      {
                        key: 'ref',
                        title: '追溯',
                        render: (row) =>
                          row.ref_id ? (
                            row.type === 'quality' ? (
                              '-'
                            ) : (
                              <Link
                                className="btn-link"
                                to={
                                  row.type === 'issue' || row.type === 'overdue'
                                    ? `/issues/${row.ref_id}`
                                    : `/inspections`
                                }
                              >
                                查看原始记录
                              </Link>
                            )
                          ) : (
                            '-'
                          ),
                      },
                    ]}
                  />
                ) : (
                  <div className="alert alert-success">当月无考核扣款。</div>
                )}
              </section>
            ) : null}

            {tab === 'inspections' ? (
              <section className="card">
                <div className="card-title">
                  <h3>纳入考核的巡查记录（{settlement.inspection_links.length} 条）</h3>
                  <span className="hint">巡查得分共同决定质量考核扣款</span>
                </div>
                {!assessed ? (
                  <div className="empty-block">考核后生成巡查明细快照。</div>
                ) : (
                  <DataTable
                    rows={settlement.inspection_links}
                    columns={[
                      {
                        key: 'inspect_time',
                        title: '巡查时间',
                        render: (row) => formatDateTime(row.inspect_time),
                      },
                      {
                        key: 'restroom_name',
                        title: '公厕',
                        render: (row) =>
                          row.restroom_id ? (
                            <Link to={`/restrooms/${row.restroom_id}`}>{row.restroom_name}</Link>
                          ) : (
                            row.restroom_name
                          ),
                      },
                      { key: 'inspector', title: '巡查人' },
                      { key: 'score', title: '得分', render: (row) => <ScorePill score={row.score} /> },
                      { key: 'grade', title: '等级', render: (row) => <GradeTag grade={row.grade} /> },
                      { key: 'result', title: '结论', render: (row) => <StatusTag status={row.result} /> },
                      { key: 'deduction_reason', title: '计入说明', wrap: true },
                    ]}
                  />
                )}
              </section>
            ) : null}

            {tab === 'issues' ? (
              <section className="card">
                <div className="card-title">
                  <h3>纳入考核的问题整改记录（{settlement.issue_links.length} 条）</h3>
                  <span className="hint">按严重程度扣款，超期未闭环追加扣款</span>
                </div>
                {!assessed ? (
                  <div className="empty-block">考核后生成问题明细快照。</div>
                ) : (
                  <DataTable
                    rows={settlement.issue_links}
                    columns={[
                      { key: 'code', title: '问题编号' },
                      {
                        key: 'title',
                        title: '问题',
                        wrap: true,
                        render: (row) =>
                          row.issue_id ? (
                            <Link to={`/issues/${row.issue_id}`}>{row.title}</Link>
                          ) : (
                            row.title
                          ),
                      },
                      {
                        key: 'restroom_name',
                        title: '公厕',
                        render: (row) =>
                          row.restroom_id ? (
                            <Link to={`/restrooms/${row.restroom_id}`}>{row.restroom_name}</Link>
                          ) : (
                            row.restroom_name
                          ),
                      },
                      { key: 'category', title: '分类' },
                      { key: 'severity', title: '程度', render: (row) => <SeverityTag severity={row.severity} /> },
                      { key: 'status', title: '考核时状态', render: (row) => <StatusTag status={row.status} /> },
                      {
                        key: 'is_overdue',
                        title: '超期',
                        render: (row) =>
                          row.is_overdue ? <span className="tag tag-danger">超期未闭环</span> : '否',
                      },
                      {
                        key: 'deduction',
                        title: '扣款（元）',
                        render: (row) => (
                          <span className={row.deduction > 0 ? 'money-negative' : ''}>
                            ¥{formatMoney(row.deduction)}
                          </span>
                        ),
                      },
                      { key: 'deduction_reason', title: '扣款原因', wrap: true },
                    ]}
                  />
                )}
              </section>
            ) : null}
          </>
        ) : null}
      </div>

      {action && settlement ? (
        <SettlementActionModal
          action={action}
          settlement={settlement}
          onClose={() => setAction(null)}
          onDone={() => {
            setAction(null);
            reload();
          }}
        />
      ) : null}
    </>
  );
}

function SettlementActionModal({ action, settlement, onClose, onDone }) {
  const toast = useToast();
  const [operator, setOperator] = useState('');
  const [remark, setRemark] = useState('');
  const [amount, setAmount] = useState(0);
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const titleMap = {
    assess: settlement.status === '待考核' ? '执行月度考核' : '重新考核',
    manual: '登记其他扣款调整',
    transition: action.option?.action,
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!operator.trim()) {
      setError('请填写操作人');
      return;
    }
    if (action.kind === 'manual' && !reason.trim()) {
      setError('请填写调整说明');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (action.kind === 'assess') {
        await settlementApi.assess(settlement.id, {
          to_status: '已考核',
          operator: operator.trim(),
          remark: remark || null,
        });
        toast.success('考核完成，扣款已按当期数据计算');
      } else if (action.kind === 'manual') {
        await settlementApi.manual(settlement.id, {
          manual_deduction: Number(amount) || 0,
          manual_reason: reason.trim(),
        });
        toast.success('扣款调整已登记');
      } else {
        await settlementApi.changeStatus(settlement.id, {
          to_status: action.option.status,
          operator: operator.trim(),
          remark: remark || null,
        });
        toast.success(`已${action.option.action}`);
      }
      onDone();
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  };

  return (
    <Modal
      title={titleMap[action.kind]}
      onClose={onClose}
      width={560}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="settlement-action-form" className="btn btn-primary" disabled={saving}>
            {saving ? '处理中…' : '确认'}
          </button>
        </>
      }
    >
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="settlement-action-form" className="form-grid" onSubmit={submit}>
        <Field label="操作人 *" full>
          <input value={operator} onChange={(event) => setOperator(event.target.value)} placeholder="考核员 / 财务科" />
        </Field>
        {action.kind === 'manual' ? (
          <>
            <Field label="调整金额（元，正数扣减、负数核增奖励）" full>
              <input
                type="number"
                step="0.01"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
              />
            </Field>
            <Field label="调整说明 *" full>
              <textarea rows="2" value={reason} onChange={(event) => setReason(event.target.value)} />
            </Field>
          </>
        ) : (
          <Field label="处理说明" full>
            <textarea
              rows="2"
              value={remark}
              onChange={(event) => setRemark(event.target.value)}
              placeholder={
                action.kind === 'assess'
                  ? '将按合同服务范围内当期巡查与问题数据重新计算扣款'
                  : undefined
              }
            />
          </Field>
        )}
      </form>
    </Modal>
  );
}
