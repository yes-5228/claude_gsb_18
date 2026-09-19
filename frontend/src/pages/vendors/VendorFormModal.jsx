import { useState } from 'react';

import { vendorApi } from '../../api/vendors.js';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../components/Toast.jsx';
import { useDictionaries } from '../../hooks/useDictionaries.js';

const EMPTY = {
  name: '',
  license_no: '',
  contact_person: '',
  contact_phone: '',
  address: '',
  status: '合作中',
  remark: '',
};

export default function VendorFormModal({ vendor, onClose, onSaved }) {
  const { dictionaries } = useDictionaries();
  const toast = useToast();
  const [form, setForm] = useState(() => ({ ...EMPTY, ...(vendor ?? {}) }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const setValue = (key) => (event) =>
    setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    if (!form.name.trim()) {
      setError('单位名称为必填项');
      return;
    }
    setSaving(true);
    setError(null);
    const payload = { ...form };
    delete payload.id;
    delete payload.code;
    delete payload.created_at;
    delete payload.updated_at;
    try {
      if (vendor?.id) {
        await vendorApi.update(vendor.id, payload);
        toast.success('外包单位已更新');
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
      width={760}
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
          <input value={form.name} onChange={setValue('name')} placeholder="如：城洁环境服务有限公司" />
        </Field>
        <Field label="合作状态">
          <select value={form.status} onChange={setValue('status')}>
            {(dictionaries?.vendor_status || ['合作中', '暂停合作', '终止合作']).map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </Field>
        <Field label="统一社会信用代码">
          <input value={form.license_no} onChange={setValue('license_no')} />
        </Field>
        <Field label="联系人">
          <input value={form.contact_person} onChange={setValue('contact_person')} />
        </Field>
        <Field label="联系电话">
          <input value={form.contact_phone} onChange={setValue('contact_phone')} />
        </Field>
        <Field label="单位地址">
          <input value={form.address} onChange={setValue('address')} />
        </Field>
        <Field label="备注" full>
          <textarea rows="2" value={form.remark || ''} onChange={setValue('remark')} />
        </Field>
      </form>
    </Modal>
  );
}
