#!/bin/sh

CODE=$1

curl http://localhost:8000/cms/product/get_by_code/"$CODE"?device_id=test

