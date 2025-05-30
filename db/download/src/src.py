import io
import os

import pandas as pd
import requests


# Dictionary of states with their respective Dropbox links
state_links = {
    # "alaska": "https://www.dropbox.com/scl/fi/46hmzd088xsfodjvrn1nd/alaska_index.csv?rlkey=sxm9twoj6e5yunourtxbtxtdf&st=9yrbcvvm&dl=1",
    "california": "https://www.dropbox.com/scl/fi/ojr27wvg0f9qzobvpbfmt/ca-index.csv?rlkey=4ahuwe2tlsl1s9ri854q0p2d4&st=00x85e8s&dl=1",
    "arizona": "https://www.dropbox.com/scl/fi/fzeinccv04sb0jocmky8y/arizona_index.csv?rlkey=porsia5lpzhg61rlb7u4kqe1d&st=fjfodsfq&dl=1",
    "florida": "https://www.dropbox.com/scl/fi/xbvuqf3sx6spr0369j5po/florida_index.csv?rlkey=qhbulvsqggtqqs1t52n5d3hbb&st=1lu4dgzm&dl=1",
    "florida-discipline": "https://www.dropbox.com/scl/fi/2iwmesdziw23ngm9bftu8/florida-discipline_index.csv?rlkey=0s0935k8dbrrnlckx2bzfnzcb&st=w0boolgj&dl=1",
    "georgia": "https://www.dropbox.com/scl/fi/zt5bjmti0ib53zret4cjl/georgia_index.csv?rlkey=vxdihmruxipj0t70qkg6gv3f3&st=vteh8461&dl=1",
    "georgia-discipline": "https://www.dropbox.com/scl/fi/pehr90qu1wl60cx0aqu1e/georgia-discipline_index.csv?rlkey=tzgj77njnkkzswgsigfhrr9w1&st=ig70k39g&dl=1",
    "idaho": "https://www.dropbox.com/scl/fi/ibxvc1eet0ugfmlpaz5sa/id-index-2025.csv?rlkey=ludawnb34zy84h4d3rvbsap12&st=dof3dp7u&dl=1",
    "illinois": "https://www.dropbox.com/scl/fi/853ypyqq4jz77569npo7w/illinois_index.csv?rlkey=6rsa807ec0an01ndna0jwvmnp&st=3l9fwzw1&dl=1",
    "indiana": "https://www.dropbox.com/scl/fi/vmgoh3ip4n8w0q582x3u8/indiana_index.csv?rlkey=yzuy32qcrnjshsqm9myfx9zm0&st=sm7yqah0&dl=1",
    "kansas": "https://www.dropbox.com/scl/fi/ybk3uwwnnx5qwbyaeugmu/ks-2024-index.csv?rlkey=i25172obz0g4sva86lmx7loep&st=dp9rdxfn&dl=1",
    "kentucky": "https://www.dropbox.com/scl/fi/vfrc4hk6rc4xxe7abbrqq/kentucky_index.csv?rlkey=jhon9hgnp0cwptndu8u6pnx5a&st=65tycia0&dl=1",
    "maryland": "https://www.dropbox.com/scl/fi/il78zwhiwr96nkjz1y6qy/maryland_index.csv?rlkey=6zaiii9fyov5qq8j8vb8oln4y&st=ff0jfo7m&dl=1",
    "minnesota": "https://www.dropbox.com/scl/fi/ziq65kq88958c7qyn7lv3/mn-index-2025-01-21.csv?rlkey=s4f9oet208tzsyrvf2pmw05y9&st=vag7v22c&dl=1",
    "mississippi": "https://www.dropbox.com/scl/fi/3wdbgs3f79y9gixhevusu/mississippi-processed.csv?rlkey=rxi3tpkxnofowtch9t9d7lx1r&st=ob5us55t&dl=1",
    "north-carolina": "https://www.dropbox.com/scl/fi/frqut5bekxdjvll4tf7re/north-carolina-processed.csv?rlkey=wifb02q85rrytjgobgz6vi5co&st=d5e1in9r&dl=1",
    "new-mexico": "https://www.dropbox.com/scl/fi/jn2qpe6ipjr8ci8dwgukn/new-mexico-preprocessed.csv?rlkey=cyr4myzdhbep5wenfy3frxo34&st=00rifhho&dl=1",
    "ohio": "https://www.dropbox.com/scl/fi/mt6i1x4lo8unl4emt1kbs/ohio-processed.csv?rlkey=v5vbmez1uo9ncxqau98s49mvh&st=o9i4abo6&dl=1",
    "oregon": "https://www.dropbox.com/scl/fi/6bhtcbs4u0i4zv0odj62v/oregon_index.csv?rlkey=w2gcmt61xmnhlu8hyc7b9ybci&st=t5vydjay&dl=1",
    "south-carolina": "https://www.dropbox.com/scl/fi/j3c6mioqjmxddv1cs6602/south_carolina_index.csv?rlkey=w0d2crkkdjhleal88zxe16tzr&st=1fmrbk16&dl=1",
    "tennessee": "https://www.dropbox.com/scl/fi/lxz9ocw7gr2qsaexc3cbh/tennessee_index.csv?rlkey=vqgsf94kre0bexaf3rf97np9o&st=gatjace4&dl=1",
    "texas": "https://www.dropbox.com/scl/fi/9257upb2n6inzs5sbwbz8/texas_index.csv?rlkey=ulz5ws8qyn0mmzs2feuvtz3c3&st=1jud1usv&dl=1",
    "utah": "https://www.dropbox.com/scl/fi/fmvoa5fvehuhcxuo1kn2n/utah_index.csv?rlkey=itmztmc6mcohioum0gpjwztdw&st=296tbj2w&dl=1",
    "vermont": "https://www.dropbox.com/scl/fi/39hyl81d50bwqu53dyecy/vermont_index.csv?rlkey=3zn94khz6lvmc3eqn77036zf5&st=exsgi7uv&dl=1",
    "washington": "https://www.dropbox.com/scl/fi/mbrnx3i8nj4mj0mlqmlpf/wa-2024-npi-index.csv?rlkey=qxf7zmirlymorffy6lr3g1cyr&st=ctacphpc&dl=1",
    "west-virginia": "https://www.dropbox.com/scl/fi/u7zgefuif53b361t9l4tt/west-virginia-processed.csv?rlkey=ittowcmmk6oeigzho1obypzcz&st=c9jlb202&dl=1",
    "wyoming": "https://www.dropbox.com/scl/fi/4c0bb071llxee25vzw4vm/wyoming_index.csv?rlkey=1ihzu4lme06urgrszldkdg0ns&st=gduoqyhf&dl=1",
}

if __name__ == "__main__":
    # Directory to save the CSV files
    output_dir = "data/output"

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
