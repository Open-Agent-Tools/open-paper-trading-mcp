from distutils.core import setup

setup(
    name="paperbroker",
    version="0.1.3",
    description="PaperBroker",
    author="Philip ODonnell",
    author_email="philip@postral.com",
    url="https://github.com/philipodonnell/paperbroker",
    packages=[
        "paperbroker",
        "paperbroker.adapters",
        "paperbroker.adapters.accounts",
        "paperbroker.adapters.quotes",
        "paperbroker.adapters.markets",
        "paperbroker.logic",
    ],
    install_requires=[
        "ivolat3",
        "arrow",
        "googlefinance",
        "flask",
        "jsonpickle",
        "requests",
    ],
)
