import request from './request'

export const uploadFile = (file: File, module: string) => {
  const form = new FormData()
  form.append('file', file)
  form.append('module', module)
  return request.post<unknown, { url: string }>('/files/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
