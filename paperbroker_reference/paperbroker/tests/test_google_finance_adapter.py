import unittest

from ..adapters.quotes import GoogleFinanceQuoteAdapter


class TestGoogleFinanceAdapter(unittest.TestCase):
    #    def __init__(self):

    #        super(TestGetQuotes, self).__init__()

    def test_get_quote(self):
        quote_adapter = GoogleFinanceQuoteAdapter()
        quote = quote_adapter.get_quote("GOOG")
        self.assertGreater(quote.price, 0)

    def test_get_expirations(self):
        quote_adapter = GoogleFinanceQuoteAdapter()
        exp = quote_adapter.get_expiration_dates("AAPL")
        options = quote_adapter.get_options("AAPL", exp[0])
        quote = quote_adapter.get_quote(options[0].asset)

        self.assertGreater(quote.price, 0)
        self.assertEqual(quote.asset.underlying, "AAPL")
        self.assertEqual(quote.asset, options[0].asset)


if __name__ == "__main__":
    unittest.main()
