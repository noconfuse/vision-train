"""打包目录为临时 ZIP 并在响应后清理文件。"""

from flask import after_this_request, send_file
from shared.utils.fs_utils import remove_file_silent


def _cleanup_temp_file(response, file_path):
    """在响应结束后删除临时压缩文件。"""
    remove_file_silent(file_path)
    return response
def send_temp_zip(zip_path, download_name):
    """发送临时 ZIP 文件并注册响应后清理。"""
    after_this_request(lambda response: _cleanup_temp_file(response, zip_path))
    try:
        return send_file(
            zip_path,
            mimetype="application/zip",
            as_attachment=True,
            download_name=download_name,
        )
    except TypeError:
        return send_file(
            zip_path,
            mimetype="application/zip",
            as_attachment=True,
            attachment_filename=download_name,
        )
