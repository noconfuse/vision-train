// 认证相关接口（自动 unwrap：拿到的就是业务数据，不是 {success, data, error}）
import { post, get, del } from './index';

export const authApi = {
  status() {
    return get('/auth/status');
  },
  login(username, password) {
    return post('/auth/login', { username, password });
  },
  logout() {
    return post('/auth/logout');
  },
  me() {
    return get('/auth/me');
  },
  changePassword(oldPassword, newPassword) {
    return post('/auth/change_password', {
      old_password: oldPassword,
      new_password: newPassword,
    });
  },
  register(data) {
    return post('/auth/register', data);
  },
  listUsers() {
    return get('/auth/users');
  },
  deleteUser(id) {
    return del(`/auth/users/${id}`);
  },
};
