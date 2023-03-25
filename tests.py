import pytest
from main import app
import requests

app.run(debug=True)

"""
curl --location 'http://127.0.0.1:5000/register' \
--header 'Content-Type: application/json' \
--data-raw '{
    "email":"test@gmail.com",
    "password":"1234",
    "name": "thomas prior"
    }'
    """

url = "http://127.0.0.1:5000/register"
data = {
    "data": {
        "email": "test@gmail.com",
        "password": "1234",
        "Sname": "tom",
    }
}

response = requests.request("POST", url, data=data)

print(response.text)