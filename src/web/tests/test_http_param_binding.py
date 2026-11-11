"""接口参数绑定：默认值必须和请求值走同一条归一化通道。"""

import unittest

from app.http import json_body_params, param, query_params
from flask import Flask


class HttpParamBindingTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_query_default_is_transformed(self):
        with self.app.test_request_context("/"):
            bound = query_params(
                offset=param("offset", default="0", transform=int),
                limit=param("limit", default="50", transform=int),
            )
        self.assertEqual(bound["offset"], 0)
        self.assertEqual(bound["limit"], 50)

    def test_query_value_still_transforms(self):
        with self.app.test_request_context("/?offset=10&limit=5"):
            bound = query_params(
                offset=param("offset", default="0", transform=int),
                limit=param("limit", default="50", transform=int),
            )
        self.assertEqual((bound["offset"], bound["limit"]), (10, 5))

    def test_json_body_factory_default_keeps_its_shape(self):
        with self.app.test_request_context(
            "/", method="POST", json={"accept": [1, 2]}
        ):
            bound = json_body_params(
                accept=param("accept", default=list),
                reject=param("reject", default=list),
            )
        self.assertEqual(bound["accept"], [1, 2])
        self.assertEqual(bound["reject"], [])


if __name__ == "__main__":
    unittest.main()
