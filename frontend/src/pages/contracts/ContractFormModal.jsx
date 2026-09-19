import { useMemo, useState } from 'react';

import { contractApi } from '../../api/contracts.js';
import { metaApi } from '../../api/meta.js';
import { vendorApi } from '../../api/vendors.js';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useAsync } from '../../hooks/useAsync.js';

function toDateInput(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (num) => String(num).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

const EMPTY = {
  code: '',
  name: '',
  vendor_id: '',
  service_scope: '',
  start_date: '',
  end_date: '',
  signed_date: '',
  monthly_fee: 0,
  payment_terms: '按月考核结算，次月 15 日前支付',
  restroom_ids: [],
  remark: '',
};

export default function ContractFormModal({ contract, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState(() => ({
    ...EMPTY,
    ...(contract
      ? {
          ...contract,
          vendor_id: contract.vendor_id ?? '',
          start_date: toDateInput(contract.start_date),
          end_date: toDateInput(contract.end_date),
          signed_date: toDateInput(contract.signed_date),
          restroom_ids: (contract.restrooms || []).map((room) => room.id),
        }
      : {}),
  }));
  const [roomKeyword, setRoomKeyword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const { data: vendors } = useAsync(() => vendorApi.options(), []);
  const { data: restrooms } = useAsync(() => metaApi.restroomOptions(''), []);

  const grouped = useMemo(() => {
    const keyword = roomKeyword.trim();
    const rows = (restrooms || []).filter(
      (room) =>
        !keyword || room.name.includes(keyword) || room.code.includes(keyword) || room.district.includes(keyword),
    );
    const map = new Map();
    rows.forEach((room) => {
      if (!map.has(room.district)) map.set(room.district, []);
      map.get(room.district).push(room);
    });
    return [...map.entries()];
  }, [restrooms, roomKeyword]);

  const setValue = (key) => (event) => {
    const target = event.target;
    const value = target.type === 'number' ? Number(target.value) : target.value;
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const toggleRestroom = (id) => {
    setForm((prev) => {
      const exists = prev.restroom_ids.includes(id);
      return {
        ...prev,
        restroom_ids: exists
          ? prev.restroom_ids.filter((item) => item !== id)
          : [...prev.restroom_ids, id],
      };
    });
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.name.trim() || !form.start_date || !form.end_date) {
      setError('合同名称、开始与到期日期为必填项');
      return;
    }
    if (!contract && !form.vendor_id) {
      setError('请选择承包单位');
      return;
    }
    const districts = [
      ...new Set(
        (restrooms || [])
          .filter((room) => form.restroom_ids.includes(room.id))
          .map((room) => room.district),
      ),
    ];
    const payload = {
      ...form,
      scope_districts: districts,
      vendor_id: contract ? undefined : Number(form.vendor_id),
      monthly_fee: Number(form.monthly_fee || 0),
    };
    if (!payload.code) payload.code = null;
    delete payload.id;
    delete payload.created_at;
    delete payload.updated_at;
    delete payload.vendor;
    delete payload.restrooms;
    delete payload.status;
    delete payload.terminate_reason;

    setSaving(true);
    setError(null);
    try {
      if (contract?.id) {
        delete payload.vendor_id;
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
      title={contract?.id ? `编辑合同 - ${contract.code}` : '登记外包合同'}
      onClose={onClose}
      width={860}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="contract-form" className="btn btn-primary" disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </button>
        </>
      }
    >
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="contract-form" className="form-grid" onSubmit={submit}>
        <Field label="承包单位 *">
          <select
            value={form.vendor_id}
            onChange={setValue('vendor_id')}
            disabled={Boolean(contract?.id)}
          >
            <option value="">请选择外包单位</option>
            {(vendors || []).map((vendor) => (
              <option key={vendor.id} value={vendor.id}>
                {vendor.name}（{vendor.code}）
              </option>
            ))}
          </select>
        </Field>
        <Field label="合同编号" hint="留空自动生成 HT-0001">
          <input value={form.code || ''} onChange={setValue('code')} disabled={Boolean(contract?.id)} placeholder="自动生成" />
        </Field>
        <Field label="合同名称 *" full>
          <input value={form.name} onChange={setValue('name')} placeholder="如：城东区公厕保洁外包服务合同" />
        </Field>
        <Field label="开始日期 *">
          <input type="date" value={form.start_date} onChange={setValue('start_date')} />
        </Field>
        <Field label="到期日期 *">
          <input type="date" value={form.end_date} onChange={setValue('end_date')} />
        </Field>
        <Field label="签订日期">
          <input type="date" value={form.signed_date || ''} onChange={setValue('signed_date')} />
        </Field>
        <Field label="月度服务费（元） *">
          <input type="number" min="0" step="0.01" value={form.monthly_fee} onChange={setValue('monthly_fee')} />
        </Field>
        <Field label="付款约定" full>
          <input value={form.payment_terms} onChange={setValue('payment_terms')} />
        </Field>
        <Field label="服务范围说明" full>
          <textarea
            rows="2"
            value={form.service_scope}
            onChange={setValue('service_scope')}
            placeholder="如：辖区 3 座公厕日常保洁、耗材补给与垃圾清运"
          />
        </Field>
        <Field label="服务公厕（勾选纳入合同范围）" full>
          <div className="scope-picker">
            <input
              value={roomKeyword}
              placeholder="按名称 / 编号 / 区域筛选公厕"
              onChange={(event) => setRoomKeyword(event.target.value)}
            />
            <div className="scope-options">
              {grouped.length === 0 ? <div className="muted">未找到匹配的公厕</div> : null}
              {grouped.map(([district, rooms]) => (
                <div key={district} className="scope-group">
                  <div className="scope-district">{district}</div>
                  <div className="scope-items">
                    {rooms.map((room) => (
                      <label key={room.id} className="scope-item">
                        <input
                          type="checkbox"
                          checked={form.restroom_ids.includes(room.id)}
                          onChange={() => toggleRestroom(room.id)}
                        />
                        <span>
                          {room.name}
                          <span className="muted">（{room.code}）</span>
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="muted" style={{ fontSize: 12 }}>
              已选 {form.restroom_ids.length} 座公厕；同一公厕在同一时段不能被两份合同重复覆盖
            </div>
          </div>
        </Field>
        <Field label="备注" full>
          <textarea rows="2" value={form.remark || ''} onChange={setValue('remark')} />
        </Field>
      </form>
    </Modal>
  );
}
