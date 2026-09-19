import { http } from './client.js';

export const vendorApi = {
  list: (params) => http.get('/vendors', params),
  options: () => http.get('/vendors/options'),
  detail: (id) => http.get(`/vendors/${id}`),
  create: (payload) => http.post('/vendors', payload),
  update: (id, payload) => http.patch(`/vendors/${id}`, payload),
  remove: (id) => http.delete(`/vendors/${id}`),
};
