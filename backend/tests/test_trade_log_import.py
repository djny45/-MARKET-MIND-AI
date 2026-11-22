import io
import unittest

from app.trade_log_import import inspect_trade_log


MAPPING = {
    "event_id": "id",
    "event_time": "time",
    "instrument": "symbol",
    "event_type": "type",
    "side": "side",
    "quantity": "qty",
    "price": "price",
    "fee": "fee",
}


class TradeLogImportTests(unittest.TestCase):
    def test_dry_run_csv_hash_counts_and_utc_normalization(self):
        body = (
            "id,time,symbol,type,side,qty,price,fee\n"
            "e1,2026-01-01T10:00:00+05:30,BTCUSD,FILL,BUY,0.2,50000,0.1\n"
            "e2,2026-01-01T05:00:00Z,BTCUSD,ACKNOWLEDGED,,,,\n"
        ).encode()
        result = inspect_trade_log(io.BytesIO(body), column_mapping=MAPPING)
        self.assertEqual(result["status"], "dry_run_only")
        self.assertEqual(result["accepted_rows"], 2)
        self.assertEqual(result["rejected_rows"], 0)
        self.assertEqual(result["sha256"], __import__("hashlib").sha256(body).hexdigest())
        self.assertEqual(result["first_event_time"], "2026-01-01T04:30:00+00:00")
        self.assertEqual(result["persistence"], "not_performed")

    def test_duplicates_are_counted_and_not_double_accepted(self):
        body = (
            "id,time,symbol,type\n"
            "e1,2026-01-01T00:00:00Z,BTCUSD,ORDER_CREATED\n"
            "e1,2026-01-01T00:01:00Z,BTCUSD,FILL\n"
        ).encode()
        mapping = {k: v for k, v in MAPPING.items() if k in {"event_id","event_time","instrument","event_type"}}
        result = inspect_trade_log(io.BytesIO(body), column_mapping=mapping)
        self.assertEqual(result["accepted_rows"], 1)
        self.assertEqual(result["duplicate_rows"], 1)

    def test_bad_rows_are_counted_without_silent_coercion(self):
        body = (
            "id,time,symbol,type,side,qty,price,fee\n"
            "e1,not-a-time,BTCUSD,FILL,BUY,1,10,0\n"
            "e2,2026-01-01T00:00:00Z,BTCUSD,FILL,BUY,-1,10,0\n"
        ).encode()
        result = inspect_trade_log(io.BytesIO(body), column_mapping=MAPPING)
        self.assertEqual(result["accepted_rows"], 0)
        self.assertEqual(result["rejected_rows"], 2)

    def test_rejects_missing_mapping_and_duplicate_source_columns(self):
        with self.assertRaisesRegex(ValueError, "must map"):
            inspect_trade_log(io.BytesIO(b"id,time\na,b\n"), column_mapping={"event_id":"id"})
        mapping = {"event_id":"id","event_time":"Time","instrument":"time","event_type":"type"}
        with self.assertRaisesRegex(ValueError, "must be unique"):
            inspect_trade_log(io.BytesIO(b"id,time,type\na,b,c\n"), column_mapping=mapping)

    def test_rejects_oversized_input_before_csv_parse(self):
        with self.assertRaisesRegex(ValueError, "exceeds configured"):
            inspect_trade_log(io.BytesIO(b"a" * 20), column_mapping={
                "event_id":"id","event_time":"time","instrument":"symbol","event_type":"type"
            }, max_bytes=10)

    def test_rejects_non_utf8_input(self):
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            inspect_trade_log(io.BytesIO(b"\xff\xfe\x00"), column_mapping={
                "event_id":"id","event_time":"time","instrument":"symbol","event_type":"type"
            })

    def test_optional_fee_currency_and_order_reference_are_preserved(self):
        body = (
            "id,time,symbol,type,side,qty,price,fee,fee_ccy,order_ref\\n"
            "e1,2026-01-01T00:00:00Z,BTCUSD,FILL,BUY,0.2,50000,0.1,USDT,ord-77\\n"
        ).encode()
        mapping = {**MAPPING, "fee_currency": "fee_ccy", "order_reference": "order_ref"}
        result = inspect_trade_log(io.BytesIO(body), column_mapping=mapping)
        self.assertEqual(result["parser_version"], "trade-event-csv-v2")
        self.assertEqual(result["sample"][0]["fee_currency"], "USDT")
        self.assertEqual(result["sample"][0]["order_reference"], "ord-77")

    def test_rejects_secret_like_optional_event_metadata(self):
        body = (
            "id,time,symbol,type,side,qty,price,fee,fee_ccy,order_ref\\n"
            "e1,2026-01-01T00:00:00Z,BTCUSD,FILL,BUY,0.2,50000,0.1,USDT,api_token_value\\n"
        ).encode()
        mapping = {**MAPPING, "fee_currency": "fee_ccy", "order_reference": "order_ref"}
        result = inspect_trade_log(io.BytesIO(body), column_mapping=mapping)
        self.assertEqual(result["accepted_rows"], 0)
        self.assertEqual(result["rejected_rows"], 1)
        self.assertNotIn("api_token_value", str(result))


if __name__ == "__main__":
    unittest.main()
