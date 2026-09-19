import { http } from './client.js';

const RESOURCE = '/vendors';

export const vendorApi = {
  list: (params) => http.get(RESOURCE, params),
  detail: (id) => http.get(`${RESOURCE}/${id}`),
  create: (payload) => http.post(RESOURCE, payload),
  update: (id, payload) => http.patch(`${RESOURCE}/${id}`, payload),
  remove: (id) => http.delete(`${RESOURCE}/${id}`),
  options: (params) => http.get(`${RESOURCE}/meta/options`, params),
};
