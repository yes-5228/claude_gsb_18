import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { settlementApi } from '../../api/settlements.js';
import DetailList from '../../components/DetailList.jsx';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { StatusTag } from '../../components/Tags.jsx';
import { useToast } from '../../components/Toast.jsx';
import { formatDateTime, formatMoney } from '../../utils/format.js';

const TYPE_LABELS = {
  score: '巡查质量',
  new_issue: '新上报问题',
  overdue: '超期未闭环',
  reject: '验收驳回',
  cap: '封顶调整',
  manual: '其他扣款',
  bonus: '考核奖励',
};

const TYPE_TONES = {
  score: 'tag-primary',
  new_issue: 'tag-warning',
  overdue: 'tag-danger',
  reject: 'tag-danger',
  cap: 'tag-neutral',
  manual: 'tag-warning',
  bonus: 'tag-success',
};

function EvidenceRef({ evidence }) {
  if (evidence.ref_type === 'issue' && evidence.ref_id) {
    return (
      <Link className="btn-link" to={`/issues/${evidence.ref_id}`} onClick={(e) => e.stopPropagation()}>
        {evidence.ref_code ? `工单 ${evidence.ref_code}` : `工单 #${evidence.ref_id}`}
        {' '}→
      </Link>
    );
  }
  if (evidence.type === 'score') {
    return <span className="muted">汇总当月全部巡查</span>;
  }
  return <span className="muted">-</span>;
}

export default function SettlementDetailModal({ settlementId, onClose, onChanged }) {
  const toast = useToast();
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ other_deduction: '', other_reason: '', bonus: '', monthly_fee: '' });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setError(null);
    try {
      const data = await settlementApi.detail(settlementId);
      setDetail(data);
      setForm({
        other_deduction: data.other_deduction || '',
        other_reason: data.other_reason || '',
        bonus: data.bonus || '',
        monthly_fee: data.monthly_fee || '',
      });
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settlementId]);

  const run = async (action, success) => {
    setBusy(true);
    try {
      await action();
      toast.success(success);
      await load();
      onChanged?.();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  const reassess = () =>
    run(() => settlementApi.reassess(settlementId), '已按最新巡查/问题数据重新考核');

  const saveAdjust = (event) => {
    event.preventDefault();
    run(
      () =>
        settlementApi.adjust(settlementId, {
          other_deduction: form.other_deduction === '' ? 0 : Number(form.other_deduction),
          other_reason: form.other_reason,
          bonus: form.bonus === '' ? 0 : Number(form.bonus),
          monthly_fee: form.monthly_fee === '' ? undefined : Number(form.monthly_fee),
        }),
      '调整已保存',
    ).then(() => setEditing(false));
  };

  const confirmSettle = () => {
    const operator = window.prompt('确认结算后金额将锁定，请填写结算确认人：');
    if (operator === null) return;
    if (!operator.trim()) {
      toast.error('请填写结算确认人');
      return;
    }
    const remark = window.prompt('结算备注（可留空）：') || '';
    run(
      () => settlementApi.confirm(settlementId, { operator: operator.trim(), remark }),
      '已确认结算',
    );
  };

  const remove = () => {
    if (!window.confirm('确认删除该结算单？仅「已考核」状态可删除。')) return;
    setBusy(true);
    settlementApi
      .remove(settlementId)
      .then(() => {
        toast.success('结算单已删除');
        onChanged?.();
        onClose();
      })
      .catch((err) => toast.error(err.message))
      .finally(() => setBusy(false));
  };

  const settled = detail?.status === '已结算';

  return (
    <Modal
      title={detail ? `结算单 ${detail.code}（${detail.period}）` : '结算单详情'}
      onClose={onClose}
      width={920}
      footer={
        detail && !settled ? (
          <>
            <button type="button" className="btn btn-danger" onClick={remove} disabled={busy}>
              删除
            </button>
            <button type="button" className="btn" onClick={reassess} disabled={busy}>
              重新考核
            </button>
            <button type="button" className="btn" onClick={() => setEditing((v) => !v)} disabled={busy}>
              {editing ? '收起调整' : '手工调整'}
            </button>
            <button type="button" className="btn btn-primary" onClick={confirmSettle} disabled={busy}>
              确认结算
            </button>
          </>
        ) : (
          <button type="button" className="btn" onClick={onClose}>
            关闭
          </button>
        )
      }
    >
      {error ? <div className="alert alert-error">{error}</div> : null}
      {!detail ? <div className="loading-block">加载中…</div> : null}

      {detail ? (
        <>
          <div className="inline" style={{ marginBottom: 12 }}>
            <StatusTag status={detail.status} />
            <span className="tag tag-primary">{detail.assess_grade || '未评级'}</span>
            <span className="muted">
              {detail.vendor_name} · {detail.contract_name}（{detail.contract_code}）
            </span>
          </div>

          <DetailList
            items={[
              { label: '月度服务费', value: `¥ ${formatMoney(detail.monthly_fee)}` },
              { label: '当月巡查次数', value: `${detail.inspection_count} 次` },
              { label: '当月巡查均分', value: detail.avg_score == null ? '无记录' : `${detail.avg_score} 分` },
              { label: '新上报问题', value: `${detail.issue_new_count} 条` },
              { label: '期末超期未闭环', value: `${detail.issue_overdue_count} 条` },
              { label: '验收驳回', value: `${detail.issue_reject_count} 次` },
              { label: '巡查质量扣款', value: `¥ ${formatMoney(detail.score_deduction)}` },
              { label: '问题整改扣款', value: `¥ ${formatMoney(detail.issue_deduction)}` },
              { label: '超期未闭环扣款', value: `¥ ${formatMoney(detail.overdue_deduction)}` },
              { label: '验收驳回扣款', value: `¥ ${formatMoney(detail.reject_deduction)}` },
              { label: '其他扣款', value: `¥ ${formatMoney(detail.other_deduction)}${detail.other_reason ? `（${detail.other_reason}）` : ''}` },
              { label: '考核奖励', value: `¥ ${formatMoney(detail.bonus)}` },
              { label: '考核人 / 时间', value: `${detail.assessor || '-'} · ${formatDateTime(detail.assess_time)}` },
              {
                label: '结算确认',
                value: settled
                  ? `${detail.settle_operator || '-'} · ${formatDateTime(detail.settle_time)}${detail.settle_remark ? `（${detail.settle_remark}）` : ''}`
                  : '尚未确认结算',
              },
            ]}
          />

          <div className="settlement-summary">
            <div>
              <span className="muted">扣款合计</span>
              <strong> ¥ {formatMoney(detail.total_deduction)}</strong>
            </div>
            <div>
              <span className="muted">应付结算金额</span>
              <strong className="money-strong"> ¥ {formatMoney(detail.payable_amount)}</strong>
            </div>
          </div>

          {editing && !settled ? (
            <form className="form-grid" style={{ marginTop: 12 }} onSubmit={saveAdjust}>
              <Field label="月度服务费调整">
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.monthly_fee}
                  onChange={(e) => setForm((p) => ({ ...p, monthly_fee: e.target.value }))}
                />
              </Field>
              <Field label="其他扣款金额">
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.other_deduction}
                  onChange={(e) => setForm((p) => ({ ...p, other_deduction: e.target.value }))}
                />
              </Field>
              <Field label="其他扣款说明">
                <input
                  value={form.other_reason}
                  onChange={(e) => setForm((p) => ({ ...p, other_reason: e.target.value }))}
                  placeholder="如：群众投诉扣罚"
                />
              </Field>
              <Field label="奖励金额">
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.bonus}
                  onChange={(e) => setForm((p) => ({ ...p, bonus: e.target.value }))}
                />
              </Field>
              <div className="full">
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  保存调整
                </button>
              </div>
            </form>
          ) : null}

          <div className="section-title">扣款依据明细（可追溯到巡查/问题记录）</div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 110 }}>类型</th>
                  <th>事项</th>
                  <th style={{ width: 120 }}>金额（元）</th>
                  <th style={{ width: 160 }}>关联记录</th>
                  <th style={{ width: 150 }}>发生时间</th>
                </tr>
              </thead>
              <tbody>
                {(detail.evidences || []).length === 0 ? (
                  <tr>
                    <td colSpan={5}>
                      <div className="empty-block">无扣款依据</div>
                    </td>
                  </tr>
                ) : (
                  detail.evidences.map((item, index) => (
                    <tr key={`${item.type}-${item.ref_id ?? index}`}>
                      <td>
                        <span className={`tag ${TYPE_TONES[item.type] || 'tag-neutral'}`}>
                          {TYPE_LABELS[item.type] || item.type}
                        </span>
                      </td>
                      <td className="wrap">{item.title}</td>
                      <td className={item.amount < 0 ? 'money-bonus' : item.amount > 0 ? 'money-deduct' : ''}>
                        {item.amount < 0 ? '+' : item.amount > 0 ? '-' : ''}
                        {formatMoney(Math.abs(item.amount))}
                      </td>
                      <td>
                        <EvidenceRef evidence={item} />
                      </td>
                      <td>{formatDateTime(item.ref_time)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {detail.assess_remark ? (
            <div className="alert alert-info" style={{ marginTop: 12 }}>
              考核说明：{detail.assess_remark}
            </div>
          ) : null}
        </>
      ) : null}
    </Modal>
  );
}
