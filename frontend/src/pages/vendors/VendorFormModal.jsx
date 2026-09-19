import { useState } from 'react';

import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { useDictionaries } from '../../hooks/useDictionaries.js';
import { vendorApi } from '../../api/vendors.js';
import { useToast } from '../../components/Toast.jsx';

const EMPTY = {
  name: '',
  code: '',
  contact_person: '',
  contact_phone: '',
  address: '',
  qualification: '',
  status: '合作中',
  remark: '',
};

export default function VendorFormModal({ vendor, onClose, onSaved }) {
  const { dictionaries } = useDictionaries();
  const toast = useToast();
  const [form, setForm] = useState(() => ({ ...EMPTY, ...(vendor ?? {}) }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const setValue = (key) => (event) => {
    setForm((prev) => ({ ...prev, [key]: event.target.value }));
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.name.trim()) {
      setError('单位名称为必填项');
      return;
    }
    setSaving(true);
    setError(null);
    const payload = { ...form };
    if (!payload.code) payload.code = null;
    delete payload.id;
    delete payload.created_at;
    delete payload.updated_at;
    try {
      if (vendor?.id) {
        await vendorApi.update(vendor.id, payload);
        toast.success('单位信息已更新');
      } else {
        await vendorApi.create(payload);
        toast.success('外包单位已登记');
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
      title={vendor?.id ? `编辑外包单位 - ${vendor.code}` : '登记外包单位'}
      onClose={onClose}
      width={720}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="vendor-form" className="btn btn-primary" disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </button>
        </>
      }
    >
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="vendor-form" className="form-grid" onSubmit={submit}>
        <Field label="单位名称 *">
          <input value={form.name} onChange={setValue('name')} placeholder="如：XX环卫服务有限公司" />
        </Field>
        <Field label="单位编号" hint="留空自动生成 WB-001">
          <input
            value={form.code || ''}
            onChange={setValue('code')}
            disabled={Boolean(vendor?.id)}
            placeholder="自动生成"
          />
        </Field>
        <Field label="联系人">
          <input value={form.contact_person} onChange={setValue('contact_person')} />
        </Field>
        <Field label="联系电话">
          <input value={form.contact_phone} onChange={setValue('contact_phone')} />
        </Field>
        <Field label="合作状态">
          <select value={form.status} onChange={setValue('status')}>
            {(dictionaries?.vendor_status || ['合作中', '已停用']).map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </Field>
        <Field label="资质等级/证书">
          <input value={form.qualification} onChange={setValue('qualification')} placeholder="如：环卫保洁服务一级资质" />
        </Field>
        <Field label="单位地址" full>
          <input value={form.address} onChange={setValue('address')} />
        </Field>
        <Field label="备注" full>
          <textarea rows="2" value={form.remark || ''} onChange={setValue('remark')} />
        </Field>
      </form>
    </Modal>
  );
}
