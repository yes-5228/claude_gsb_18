import { useEffect, useState } from 'react';

import { settlementApi } from '../../api/settlements.js';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { ScorePill } from '../../components/Tags.jsx';
import { useToast } from '../../components/Toast.jsx';
import { currentMonth, formatMoney } from '../../utils/format.js';

export default function SettlementCreateModal({ contract, onClose, onCreated }) {
  const toast = useToast();
  const [periodMonth, setPeriodMonth] = useState(currentMonth());
  const [remark, setRemark] = useState('');
  const [preview, setPreview] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const loadPreview = async () => {
    if (!contract?.id || !/^\d{4}-\d{2}$/.test(periodMonth)) return;
    setLoadingPreview(true);
    setError(null);
    try {
      const data = await settlementApi.preview(contract.id, periodMonth);
      setPreview(data);
    } catch (err) {
      setPreview(null);
      setError(err.message);
    } finally {
      setLoadingPreview(false);
    }
  };

  useEffect(() => {
    loadPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contract?.id, periodMonth]);

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const created = await settlementApi.create({
        contract_id: contract.id,
        period_month: periodMonth,
        remark: remark || null,
      });
      toast.success('月度结算单已登记，请执行考核');
      onCreated?.(created.id);
      onClose();
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  };

  return (
    <Modal
      title={`登记月度结算 - ${contract?.name ?? ''}`}
      onClose={onClose}
      width={820}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="settlement-create-form" className="btn btn-primary" disabled={saving}>
            {saving ? '登记中…' : '登记结算单'}
          </button>
        </>
      }
    >
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="settlement-create-form" className="form-grid" onSubmit={submit}>
        <Field label="考核月份 *">
          <input
            type="month"
            value={periodMonth}
            onChange={(event) => setPeriodMonth(event.target.value)}
          />
        </Field>
        <Field label="月度合同费用">
          <div className="value" style={{ paddingTop: 8 }}>
            ¥{formatMoney(contract?.monthly_fee)}
          </div>
        </Field>
        <Field label="备注" full>
          <textarea rows="2" value={remark} onChange={(event) => setRemark(event.target.value)} />
        </Field>
      </form>

      <div className="section-title">考核扣款测算（以登记时合同服务范围内的实时数据计算）</div>
      {loadingPreview ? (
        <div className="loading-block">测算中…</div>
      ) : preview ? (
        <>
          <div className="stat-grid">
            <div className="stat-card">
              <div className="label">当期巡查 / 均分</div>
              <div className="value">
                {preview.inspection_count}
                <span className="unit">次</span>
              </div>
              <div className="foot">
                均分{' '}
                {preview.avg_score != null ? <ScorePill score={preview.avg_score} /> : '无巡查'}
              </div>
            </div>
            <div className="stat-card is-warning">
              <div className="label">新增 / 超期问题</div>
              <div className="value">
                {preview.issue_count}
                <span className="unit">条</span>
              </div>
              <div className="foot">其中超期未闭环 {preview.overdue_count} 条</div>
            </div>
            <div className="stat-card is-danger">
              <div className="label">扣款合计</div>
              <div className="value" style={{ fontSize: 26 }}>
                ¥{formatMoney(preview.total_deduction)}
              </div>
              <div className="foot">
                质量 ¥{formatMoney(preview.quality_deduction)} + 问题 ¥
                {formatMoney(preview.issue_deduction + preview.overdue_deduction)}
              </div>
            </div>
            <div className="stat-card is-info">
              <div className="label">预计应结算</div>
              <div className="value" style={{ fontSize: 26 }}>
                ¥{formatMoney(preview.payable_amount)}
              </div>
              <div className="foot">月度费用扣减考核扣款</div>
            </div>
          </div>
          {preview.details.length ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>扣款项目</th>
                    <th style={{ width: 120 }}>金额（元）</th>
                    <th>计算依据</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.details.map((item, index) => (
                    <tr key={`${item.type}-${item.ref_id ?? index}`}>
                      <td>{item.name}</td>
                      <td className="money-negative">¥{formatMoney(item.amount)}</td>
                      <td className="wrap muted">{item.basis}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="alert alert-success">当月巡查质量达标且无新增问题，暂无考核扣款。</div>
          )}
        </>
      ) : null}
    </Modal>
  );
}
