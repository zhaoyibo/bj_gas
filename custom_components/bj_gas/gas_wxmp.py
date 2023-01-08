import logging
import time
import json
import asyncio
from .util.sm3 import sm3
from urllib.parse import quote

_LOGGER = logging.getLogger(__name__)

ENC_DEC_URL = "http://tool.chacuo.net/cryptdes"

WXMP_GAS_URL = "https://zt.bjgas.com:6443/wxmpgas/wxmp?data="

WXMP_APP_ID = "wx2a6065eb9e700a28"

REQ_INFO = "nbUserInfoAcctQuery"
REQ_WEK = "nbCMMWEKQryMP"
REQ_DEC = "nbCMMDECQryMP"

USER_TYPE = "04"


class AuthFailed(Exception):
    pass


class InvalidData(Exception):
    pass


class GASData:
    def __init__(self, session, wxsign, user_code):
        self._session = session
        self._wxsign = wxsign
        self._user_code = user_code
        self._info = {}

    def common_headers(self):
        headers = {
            "Host": "zt.bjgas.com:6443",
            "Connection": "keep-alive",
            # "Content-Length": "109",
            # "Tocken": "1be36023b5bd0e332b3f58e34098544539ab7fa7f8a3f6b983ff4400e3496b68",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "X-Wechat-Hostsign": f"{self._wxsign}",
            "Accept-Encoding": "gzip,compress,br,deflate",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.31(0x18001f34) NetType/WIFI Language/zh_CN",
            # "Referer": "https://servicewechat.com/wx2a6065eb9e700a28/30/page-frame.html",
        }

        return headers

    def data_concat(self, req_type):
        return req_type + "|" + self._user_code + "|" + USER_TYPE + "|" + str(
            round(time.time() * 1000)) + "|" + WXMP_APP_ID + "|"

    def encdec_headers(self):
        headers = {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Cookie": "__yjs_duid=1_98095ed0f039ff0d890013e33d1032e21673180202885; yjs_js_security_passport=ee306caa71f15b7b70cd3f9639d1639d1b4c2c41_1673180206_js",
            "Dnt": "1",
            "Origin": "http://tool.chacuo.net",
            "Referer": "http://tool.chacuo.net/cryptdes",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Accept-Encoding": "gzip",
        }
        return headers

    async def encdec(self, data, dec=1):
        headers = self.encdec_headers()

        json_data = {
            "data": f"{data}",
            "type": "des",
            "arg": f"m=cbc_pad=pkcs7_p=424A47415347464350554B414249414F_i=4D505758_o=0_s=utf-8_t={dec}",
        }

        r = await self._session.post("http://tool.chacuo.net/cryptdes", headers=headers, data=json_data, timeout=10)
        if r.status == 200:
            ret = await r.read()
            _LOGGER.warning("encdec ret:%s", ret)
            result = json.loads(ret)
            if result["status"] == 1:
                return result['data'][0]
            else:
                raise InvalidData(f"encdec error: {result}")
        else:
            raise InvalidData(f"encdec response status_code = {r.status}")

    async def async_get_week(self, user_code):
        headers = self.common_headers()

        original_data = self.data_concat(REQ_INFO)
        _LOGGER.warning("original_data:%s", original_data)
        encrypt_data = await self.encdec(original_data, 0)
        _LOGGER.warning("encrypt_data:%s", encrypt_data)
        tocken = sm3(encrypt_data).lower()
        _LOGGER.warning("tocken:%s", tocken)
        headers["Tocken"] = tocken

        urlencode_data = quote(encrypt_data)
        _LOGGER.warning("urlencode_data:%s", urlencode_data)
        r = await self._session.post(WXMP_GAS_URL + urlencode_data, headers=headers, data={"data": urlencode_data},
                                     timeout=10)
        if r.status == 200:
            ret = await r.read()
            _LOGGER.warning("gas ret:%s", ret)
            result = json.loads(ret)
            encrypt_response = result[0]['data']
            decrypt_data = await self.encdec(encrypt_response, 1)
            data_arr = decrypt_data.split('|')
            if data_arr[0] == '0001':
                self._info[user_code]["month_reg_qty"] = float(data_arr[3])
                self._info[user_code]["balance"] = float(data_arr[4])
                self._info[user_code]["current_price"] = float(data_arr[5])
                self._info[user_code]["last_update"] = data_arr[6]
                self._info[user_code]["battery_voltage"] = float(data_arr[8])
                self._info[user_code]["mtr_status"] = data_arr[9]
                if float(data_arr[16]) > 0:
                    self._info[user_code]["current_level"] = 1
                    self._info[user_code]["current_level_remain"] = float(data_arr[16])
                else:
                    self._info[user_code]["current_level"] = 2
                    self._info[user_code]["current_level_remain"] = float(data_arr[18])
                self._info[user_code]["year_consume"] = float(data_arr[19])
        else:
            raise InvalidData(f"async_get_week response status_code = {r.status}")

    async def async_get_data(self):
        self._info = {self._user_code: {}}
        tasks = [
            self.async_get_week(self._user_code),
        ]
        await asyncio.wait(tasks)
        _LOGGER.debug(f"Data {self._info}")
        return self._info
