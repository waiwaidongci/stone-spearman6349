import {request,post} from './client.js';
export const sequential={
 list:()=>request('/sequential'),
 create:x=>post('/sequential',x),
 get:id=>request(`/sequential/${id}`),
 measure:(id,x)=>post(`/sequential/${id}/measure`,x),
 ingest:id=>post(`/sequential/${id}/ingest`,{}),
};
