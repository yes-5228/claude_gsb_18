import { useState } from 'react';

import { contractApi } from '../../api/contracts.js';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { formatMoney } from '../../utils/format.js';

function monthOptions() {
  const now = new Date();
  const options = [];
  for (let offset = -2; offset <= 1; offset += 1) {
    const d = new Date(now.getFullYear(), now.getMonth() + offset, 1);
    options.push({ year: d.getFullYear(), month: d.getMonth() + 1 });
  }
  return options;
}

export default function SettlementCreateModal({ contract, onClose, onCreated }) {
  const toast = useToast();
  const periods = monthOptions();
  const current = periods[periods.length - 2] || periods[periods.length - 1];
  const [year, setYear] = useState(current.year);
  const [month, setMonth] = useState(current.month);
  const [feeOverride, setFeeOverride] = useState('');
  const [assessor, setAssessor] = useState('');
  const [remark, setRemark] = useState('');
  const [saving, setSaving] = useState(false);

  const { data: preview, error: previewError } = useAsync(
    () =>
      contractApi.assessmentPreview(contract.id, {
        year,
        month,
        monthly_fee: feeOverride === '' ? undefined : Number(feeOverride),
      }),
    [contract.id, year, month, feeOverride],
  );

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await contractApi.createSettlement(contract.id, {
        period_year: year,
        period_month: month,
        monthly_fee: feeOverride === '' ? null : Number(feeOverride),
        assessor: assessor.trim(),
        assess_remark: remark.trim() || null,
      });
      toast.success('月度考核结算单已生成');
      onCreated();
      onClose();
    } catch (err) {
      toast.error(err.message);
      setSaving(false);
    }
  };

  const rows = [
    ['巡查次数', preview ? `${preview.inspection_count} 次` : '-'],
    ['巡查均分', preview?.avg_score == null ? '无记录' : `${preview.avg_score} 分`],
    ['新上报问题', preview ? `${preview.issue_new_count} 条` : '-'],
    ['期末超期未闭环', preview ? `${preview.issue_overdue_count} 条` : '-'],
    ['验收驳回', preview ? `${preview.issue_reject_count} 次` : '-'],
  ];

  const deductions = [
    ['巡查质量扣款', preview?.score_deduction],
    ['新问题扣款', preview?.issue_deduction],
    ['超期未闭环扣款', preview?.overdue_deduction],
    ['验收驳回扣款', preview?.reject_deduction],
  ];

  return (
    <Modal
      title={`生成月度考核结算单 - ${contract.code}`}
      onClose={onClose}
      width={720}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="settlement-form" className="btn btn-primary" disabled={saving}>
            {saving ? '生成中…' : '生成结算单'}
          </button>
        </>
      }
    >
      {previewError ? <div className="alert alert-error">{previewError.message}</div> : null}
      <form id="settlement-form" className="form-grid" onSubmit={submit}>
        <Field label="考核月份 *">
          <select
            value={`${year}-${month}`}
            onChange={(event) => {
              const [y, m] = event.target.value.split('-').map(Number);
              setYear(y);
              setMonth(m);
            }}
          >
            {periods.map((item) => (
              <option key={`${item.year}-${item.month}`} value={`${item.year}-${item.month}`}>
                {item.year} 年 {item.month} 月
              </option>
            ))}
          </select>
        </Field>
        <Field label="月费用覆盖" hint="留空取合同约定月费用">
          <input
            type="number"
            min="0"
            step="0.01"
            value={feeOverride}
            placeholder={preview ? formatMoney(preview.monthly_fee) : ''}
            onChange={(event) => setFeeOverride(event.target.value)}
          />
        </Field>
        <Field label="考核人">
          <input value={assessor} onChange={(event) => setAssessor(event.target.value)} placeholder="如：考核组" />
        </Field>
        <Field label="考核说明">
          <input value={remark} onChange={(event) => setRemark(event.target.value)} />
        </Field>
      </form>

      {preview ? (
        <>
          <div className="section-title">考核测算（依据当月巡查与整改数据）</div>
          <div className="assess-grid">
            {rows.map(([label, value]) => (
              <div className="assess-cell" key={label}>
                <div className="muted">{label}</div>
                <div className="assess-value">{value}</div>
              </div>
            ))}
            <div className="assess-cell">
              <div className="muted">考核等级</div>
              <div className="assess-value">{preview.assess_grade}</div>
            </div>
          </div>
          <div className="detail-list">
            {deductions.map(([label, value]) => (
              <div className="detail-item" key={label}>
                <div className="label">{label}</div>
                <div className="value">¥ {formatMoney(value || 0)}</div>
              </div>
            ))}
            <div className="detail-item">
              <div className="label">
                <strong>扣款合计</strong>
              </div>
              <div className="value">
                <strong>¥ {formatMoney(preview.total_deduction)}</strong>
              </div>
            </div>
            <div className="detail-item">
              <div className="label">
                <strong>预计应付金额</strong>
              </div>
              <div className="value">
                <strong className="money-strong">¥ {formatMoney(preview.payable_amount)}</strong>
              </div>
            </div>
          </div>
          <div className="muted" style={{ fontSize: 12 }}>
            生成后可在结算单中查看每一笔扣款对应的巡查/问题依据；未确认结算前支持重新考核与手工调整。
          </div>
        </>
      ) : (
        <div className="loading-block">测算中…</div>
      )}
    </Modal>
  );
}
