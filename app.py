import datetime
import json
import operator
from flask import Flask, request, jsonify
from flasgger import Swagger
import requests
import pandas as pd
import jellyfish

app = Flask(__name__)
swagger = Swagger(app, template_file='swagger_config.yml')

proxies = {
    # Buraya proxyler yazılacak
    'http': '213.219.198.69:80',
    # 'https': '121.134.159.87:8080',
}


@app.route("/", methods=['GET'])
def index():
    return f"{datetime.datetime.now()} API is running"


@app.route('/parcel_data_by_coords', methods=['GET'])
def parcel_data_by_coords():
    latitude = request.args.get('latitude')
    longitude = request.args.get('longitude')
    try:
        response = requests.get(f'https://cbsapi.tkgm.gov.tr/megsiswebapi.v3/api/parsel/{latitude}/{longitude}',
                                proxies=proxies)
        # response = requests.get(f'https://cbsapi.tkgm.gov.tr/megsiswebapi.v3/api/parsel/{latitude}/{longitude}')
        data = json.loads(response.text)

        if response.status_code == 200:
            return jsonify(data)
        elif response.status_code == 404:
            return jsonify(message="Parsel verisi bulunamadı.")
        elif response.status_code == 403:
            return jsonify(message="Günlük sorgu limitini aştınız.")

    except Exception as e:
        return str(e), 500


@app.route('/parcel_data_by_location', methods=['GET'])
def parcel_data_by_location():
    city = request.args.get("city")
    district = request.args.get("district")
    neighbourhood = request.args.get("neighbourhood")
    block_no = request.args.get("block")
    parcel_no = request.args.get("parcel")

    if city and district and neighbourhood and block_no and parcel_no:
        il_, ilce_, mahalle_, mahalle_id = get_mahalle_id(city, district, neighbourhood)

        if il_[1] < 0.75 or abs(len(il_[0]) - len(city)) >= 3:
            return jsonify("Hatalı il bilgisi girildi.")
        if ilce_[1] < 0.75 or abs(len(ilce_[0]) - len(district)) >= 3:
            return jsonify("Hatalı ilce bilgisi girildi.")
        if mahalle_[1] < 0.75 or abs(len(mahalle_[0]) - len(neighbourhood)) >= 3:
            return jsonify("Hatalı mahalle bilgisi girildi.")
        else:
            try:
                response = requests.get(
                    f"https://cbsapi.tkgm.gov.tr/megsiswebapi.v3/api/parsel/{mahalle_id}/{block_no}/{parcel_no}",
                    proxies=proxies)
                data = response.json()

                if response.status_code == 200:
                    return jsonify(data)
                elif response.status_code == 404:
                    return jsonify(message="Parsel verisi bulunamadı.")
                elif response.status_code == 403:
                    return jsonify(message="Günlük sorgu limitini aştınız.")
            except Exception as e:
                return jsonify(e), 500
    else:
        return "Eksik parametre girildi", 404


def get_mahalle_id(il_req, ilce_req, mahalle_req):
    df = pd.read_csv("il_ilce_mahalle_veri.csv")

    il_skor = []
    for il in df.il.unique():
        il_skor.append((il, jellyfish.jaro_similarity(il_req.lower().strip(), il)))
    il_ = max(il_skor, key=operator.itemgetter(1))

    ilce_skor = []
    for ilce in df[df.il == il_[0]].ilce.unique():
        ilce_skor.append((ilce, jellyfish.jaro_similarity(ilce_req.lower().strip(), ilce)))
    ilce_ = max(ilce_skor, key=operator.itemgetter(1))

    mahalle_skor = []
    for mahalle in df[(df.ilce == ilce_[0]) & (df.il == il_[0])].mahalle.unique():
        _strip_mahalle = mahalle_req.lower().strip()
        if _strip_mahalle:
            mahalle_skor.append((mahalle, jellyfish.jaro_similarity(_strip_mahalle, mahalle)))
    mahalle_ = max(mahalle_skor, key=operator.itemgetter(1))

    mahalle_id = df.mahalle_id[(df.il == il_[0]) & (df.ilce == ilce_[0]) & (df.mahalle == mahalle_[0])].iloc[0]

    return il_, ilce_, mahalle_, mahalle_id


if __name__ == '__main__':
    app.run()
