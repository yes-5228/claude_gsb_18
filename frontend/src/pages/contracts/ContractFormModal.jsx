import { useEffect, useState } from 'react';

import { contractApi } from '../../api/contracts.js';
import { metaApi } from '../../api/meta.js';
import { restroomApi } from '../../api/restrooms.js';
import { vendorApi } from '../../api/vendors.js';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../components/Toast.jsx';
import { formatMoney } from '../../utils/format.js';

const EMPTY = {
  vendor_id: '',
  name: '',
  scope_type: '按区域',
  scope_districts: [],
  scope_restroom_ids: [],
  start_date: '',
  end_date: '',
  monthly_fee: 0,
  payment_terms: '次月完成考核后据实结算',
  signed_at: '',
  remark: '',
};

export default function ContractFormModal({ contract, onClose, onSaved, presetVendorId }) {
  const toast = useToast();
  const [vendors, setVendors] = useState([]);
  const [districts, setDistricts] = useState([]);
  const [restrooms, setRestrooms] = useState([]);
  const [form, setForm] = useState(() => {
    const base = { ...EMPTY, ...(contract ?? {}) };
    if (presetVendorId) base.vendor_id = Number(presetVendorId);
    return base;
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      vendorApi.options({ active_only: true }),
      restroomApi.districts(),
      metaApi.restroomOptions(),
    ])
      .then(([vendorRows, districtRows, restroomRows]) => {
        setVendors(vendorRows);
        setDistricts(districtRows);
        setRestrooms(restroomRows);
      })
      .catch((err) => setError(err.message));
  }, []);

  const setValue = (key) => (event) =>
    setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const toggleDistrict = (district) => {
    setForm((prev) => ({
      ...prev,
      scope_districts: prev.scope_districts.includes(district)
        ? prev.scope_districts.filter((item) => item !== district)
        : [...prev.scope_districts, district],
    }));
  };

  const toggleRestroom = (id) => {
    setForm((prev) => ({
      ...prev,
      scope_restroom_ids: prev.scope_restroom_ids.includes(id)
        ? prev.scope_restroom_ids.filter((item) => item !== id)
        : [...prev.scope_restroom_ids, id],
    }));
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.vendor_id) return setError('请选择承包单位');
    if (!form.name.trim()) return setError('请填写合同名称');
    if (!form.start_date || !form.end_date) return setError('请填写合同起止日期');
    if (form.end_date <= form.start_date) return setError('结束日期必须晚于开始日期');
    if (form.scope_type === '按区域' && !form.scope_districts.length)
      return setError('按区域承包时至少勾选一个服务区域');
    if (form.scope_type === '指定公厕' && !form.scope_restroom_ids.length)
      return setError('指定公厕承包时至少勾选一座公厕');

    setSaving(true);
    setError(null);
    const payload = {
      ...form,
      vendor_id: Number(form.vendor_id),
      monthly_fee: Number(form.monthly_fee) || 0,
      scope_districts: form.scope_type === '按区域' ? form.scope_districts : [],
      scope_restroom_ids: form.scope_type === '指定公厕' ? form.scope_restroom_ids : [],
    };
    delete payload.id;
    delete payload.code;
    delete payload.status;
    delete payload.effective_status;
    delete payload.scope_text;
    delete payload.scope_restroom_count;
    try {
      if (contract?.id) {
        await contractApi.update(contract.id, payload);
        toast.success('合同已更新');
      } else {
        await contractApi.create(payload);
        toast.success('合同已登记');
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={contract?.id ? `编辑合同 - ${contract.code}` : '登记保洁外包合同'}
      onClose={onClose}
      width={900}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="contract-form" className="btn btn-primary" disabled={saving}>
            {saving ? '保存中…' : '保存合同'}
          </button>
        </>
      }
    >
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="contract-form" className="form-grid" onSubmit={submit}>
        <Field label="承包单位 *">
          <select value={form.vendor_id} onChange={setValue('vendor_id')}>
            <option value="">请选择外包单位</option>
            {vendors.map((item) => (
              <option key={item.id} value={item.id}>
                {item.code} {item.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="合同名称 *">
          <input value={form.name} onChange={setValue('name')} placeholder="如：公厕保洁服务外包合同（城东区）" />
        </Field>
        <Field label="合同开始日期 *">
          <input type="date" value={form.start_date ? form.start_date.slice(0, 10) : ''} onChange={setValue('start_date')} />
        </Field>
        <Field label="合同结束日期 *">
          <input type="date" value={form.end_date ? form.end_date.slice(0, 10) : ''} onChange={setValue('end_date')} />
        </Field>
        <Field label="月度服务费用（元）*">
          <input
            type="number"
            min="0"
            step="100"
            value={form.monthly_fee}
            onChange={setValue('monthly_fee')}
          />
        </Field>
        <Field label="签订日期">
          <input
            type="date"
            value={form.signed_at ? form.signed_at.slice(0, 10) : ''}
            onChange={setValue('signed_at')}
          />
        </Field>
        <Field label="结算与付款约定" full>
          <input value={form.payment_terms} onChange={setValue('payment_terms')} />
        </Field>

        <Field label="服务范围方式" full>
          <div className="inline">
            {['按区域', '指定公厕'].map((type) => (
              <label key={type} className="checkbox-row" style={{ marginRight: 24 }}>
                <input
                  type="radio"
                  name="scope_type"
                  checked={form.scope_type === type}
                  onChange={() =>
                    setForm((prev) => ({
                      ...prev,
                      scope_type: type,
                      scope_districts: [],
                      scope_restroom_ids: [],
                    }))
                  }
                />
                {type}
              </label>
            ))}
          </div>
        </Field>

        {form.scope_type === '按区域' ? (
          <Field label="服务区域（可多选）*" full>
            <div className="pick-box">
              {districts.length ? (
                districts.map((district) => (
                  <label key={district} className="checkbox-row pick-item">
                    <input
                      type="checkbox"
                      checked={form.scope_districts.includes(district)}
                      onChange={() => toggleDistrict(district)}
                    />
                    {district}
                  </label>
                ))
              ) : (
                <span className="muted">暂无区域，请先在公厕台账中建档</span>
              )}
            </div>
          </Field>
        ) : (
          <Field label="指定公厕（可多选）*" full>
            <div className="pick-box pick-box-tall">
              {restrooms.map((room) => (
                <label key={room.id} className="checkbox-row pick-item">
                  <input
                    type="checkbox"
                    checked={form.scope_restroom_ids.includes(room.id)}
                    onChange={() => toggleRestroom(room.id)}
                  />
                  {room.code} {room.name}（{room.district}）
                </label>
              ))}
            </div>
          </Field>
        )}

        <Field label="备注" full>
          <textarea rows="2" value={form.remark || ''} onChange={setValue('remark')} />
        </Field>
      </form>
      {form.monthly_fee ? (
        <div className="hint" style={{ textAlign: 'right' }}>
          年度合同金额约 ¥{formatMoney(Number(form.monthly_fee) * 12)}（考核扣款前）
        </div>
      ) : null}
    </Modal>
  );
}
