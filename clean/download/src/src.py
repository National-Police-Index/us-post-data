import io
import os

import pandas as pd
import requests


# Dictionary of states with their respective Dropbox links
state_links = {
    "alaska": "https://www.dropbox.com/scl/fi/46hmzd088xsfodjvrn1nd/alaska_index.csv?rlkey=sxm9twoj6e5yunourtxbtxtdf&st=9yrbcvvm&dl=1",
    "arizona": "https://www.dropbox.com/scl/fi/7l9iaj2qbzq2i0azey2fl/arizona_index.csv?rlkey=2kvtnw5iaonixm08i922c5yw0&st=01o4r4j0&dl=1",
    "california": "https://www.dropbox.com/scl/fi/ait32murofp7b360p9hni/california_index.csv?rlkey=vup9ugrdrbne4kf9mdzuiocle&st=7ud05clp&dl=1",
    "florida": "https://www.dropbox.com/scl/fi/kxka39be3jgv3srbn1f73/florida_index.csv?rlkey=afrejm92m8hs0dxm4x72qq8bn&st=vmvj677c&dl=1",
    "georgia": "https://www.dropbox.com/scl/fi/20w121u4y0he9jq1j2psu/georgia_index.csv?rlkey=btvxikx1glfxg16hpvvmxtqc1&st=49ityxa5&dl=1",
    "idaho": "https://www.dropbox.com/scl/fi/f2zr19a3rgil24xhvmcj4/idaho_index.csv?rlkey=6x2j6rkr503e3k5627j459eyf&st=1img7u6b&dl=1",
    "illinois": "https://www.dropbox.com/scl/fi/853ypyqq4jz77569npo7w/illinois_index.csv?rlkey=6rsa807ec0an01ndna0jwvmnp&st=3l9fwzw1&dl=1",
    "indiana": "https://www.dropbox.com/scl/fi/vmgoh3ip4n8w0q582x3u8/indiana_index.csv?rlkey=yzuy32qcrnjshsqm9myfx9zm0&st=8xscumxw&dl=0",
    "kansas": "https://www.dropbox.com/scl/fi/mqst15jw3wh0qbeqvaeko/ks-2022-index.csv?rlkey=e03f23fjdht8q97sdiptiow6z&st=70upzfed&dl=0",
    "kentucky": "https://www.dropbox.com/scl/fi/wnlfju2e7jmkg25xudvtc/kentucky_index.csv?rlkey=fmz2x3dujtajhrgeguvz8sjzx&st=mbw1oc6o&dl=0",
    "maryland": "https://www.dropbox.com/scl/fi/p2u4254laj2kp1ruze5h3/maryland_index.csv?rlkey=ng77xq0b0wxe5z7pwu4gmzxt4&st=oedklcmp&dl=1",
    "north_carolina": "https://www.dropbox.com/scl/fi/jjinf4bfyk5umweq203bh/north_carolina_index.csv?rlkey=yrcwnb442xgpbi1ybvrsk6ur8&st=s2ffmcxt&dl=1",
    "new_mexico": "https://www.dropbox.com/scl/fi/ud8lsz7gczmdomiqbgbru/new_mexico_index.csv?rlkey=byk4erkpozp8ugshkneus7pzc&st=dydvr966&dl=1",
    "ohio": "https://www.dropbox.com/scl/fi/nxdwwcuo2c4mz2igxyzrl/ohio_index.csv?rlkey=rne8ji1x4rarh2zggsuz6pnng&st=89fm02rd&dl=1",
    "oregon": "https://www.dropbox.com/scl/fi/6bhtcbs4u0i4zv0odj62v/oregon_index.csv?rlkey=w2gcmt61xmnhlu8hyc7b9ybci&st=t5vydjay&dl=1",
    "south_carolina": "https://www.dropbox.com/scl/fi/j3c6mioqjmxddv1cs6602/south_carolina_index.csv?rlkey=w0d2crkkdjhleal88zxe16tzr&st=1fmrbk16&dl=1",
    "tennessee": "https://www.dropbox.com/scl/fi/0dk91k4exbuyiqvxgvmbt/tennessee_index.csv?rlkey=gdmlku4csh4lf8l39fv5zr4za&st=5zs52d8j&dl=1",
    "texas": "https://www.dropbox.com/scl/fi/9257upb2n6inzs5sbwbz8/texas_index.csv?rlkey=ulz5ws8qyn0mmzs2feuvtz3c3&st=1jud1usv&dl=1",
    "utah": "https://www.dropbox.com/scl/fi/yizi8kmdi7mt2nyleffj8/utah_index.csv?rlkey=syhxhallr63rs6lpjesmihteh&st=smaqhvmt&dl=1",
    "vermont": "https://www.dropbox.com/scl/fi/pyqy5p3srsp2tcjfwq865/vermont_index.csv?rlkey=t589hmxphf2movo3adwt1wrzn&st=psfk7k8p&dl=1",
    "washington": "https://www.dropbox.com/scl/fi/7hrjnpbrgq6iw4bbgozbv/washington_index.csv?rlkey=shs9lpp2vmq38d3gttvp8d65g&st=gcj67okf&dl=1",
    "west_virginia": "https://www.dropbox.com/scl/fi/iubdg5lxd3vf29sfbrwyu/west_virginia_index.csv?rlkey=g8r9fwgxp36xhd9h508n5ztfz&st=aq9zl624&dl=1",
    "wyoming": "https://www.dropbox.com/scl/fi/p3rpali2bohcesxko88yc/wyoming_index.csv?rlkey=9do9v4w0qu8g7qdnzwdqdffgx&st=v2svhbe6&dl=0",
}

# Directory to save the CSV files
output_dir = "../data/output"

# Create the directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# Download and save the CSV files
for state, url in state_links.items():
    state_dir = os.path.join(output_dir, state)
    os.makedirs(state_dir, exist_ok=True)
    file_path = os.path.join(state_dir, f"{state}_index.csv")

    # Check if the file already exists
    if os.path.exists(file_path):
        print(f"{file_path} already exists. Skipping download.")
        continue

    # Download the file if it doesn't exist
    response = requests.get(url)
    response.raise_for_status()  # Ensure the download was successful

    # Read the CSV file into a pandas DataFrame
    csv_data = pd.read_csv(io.StringIO(response.text))

    # Save the DataFrame to a CSV file
    csv_data.to_csv(file_path, index=False)

    print(f"Saved {state} data to {file_path}")
