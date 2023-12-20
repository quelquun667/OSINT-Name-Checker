import requests
import sys
from colorama import init, Fore, Style
import os


try:
    import requests
    from colorama import init, Fore, Style
except ImportError:
    os.system('pip install requests')
    os.system('pip install colorama')

    # Redémarre le script pour charger les librairies installées
    os.system('python script.py ' + ' '.join(sys.argv[1:]))
    sys.exit()

# Efface la console (cmd)
os.system('cls' if os.name == 'nt' else 'clear')


# Initialisation de colorama
init(autoreset=True)

def verifier_disponibilite_pseudo(url, pseudo):
    try:
        response = requests.get(url + pseudo)
        if response.status_code == 404:
            print(f"{Fore.RED}{url.split('//')[-1].split('/')[0]}{Style.RESET_ALL}")
            return url.split('//')[-1].split('/')[0]
        else:
            print(f"{Fore.GREEN}{url.split('//')[-1].split('/')[0]}{Style.RESET_ALL}")
    except requests.RequestException as e:
        print(f"{Fore.YELLOW}{url.split('//')[-1].split('/')[0]} (Erreur de connexion){Style.RESET_ALL}")  # Nom du site en orange

# Exemple d'utilisation avec des liens
liens = [
    "https://www.instagram.com/",
    "https://www.tiktok.com/@",
    # Ajoutez d'autres liens ici
]

art = f"""███▄    █  ▄▄▄       ███▄ ▄███▓▓█████     ▄████▄   ██░ ██ ▓█████  ▄████▄   ██ ▄█▀▓█████  ██▀███
 ██ ▀█   █ ▒████▄    ▓██▒▀█▀ ██▒▓█   ▀    ▒██▀ ▀█  ▓██░ ██▒▓█   ▀ ▒██▀ ▀█   ██▄█▒ ▓█   ▀ ▓██ ▒ ██▒
▓██  ▀█ ██▒▒██  ▀█▄  ▓██    ▓██░▒███      ▒▓█    ▄ ▒██▀▀██░▒███   ▒▓█    ▄ ▓███▄░ ▒███   ▓██ ░▄█ ▒
▓██▒  ▐▌██▒░██▄▄▄▄██ ▒██    ▒██ ▒▓█  ▄    ▒▓▓▄ ▄██▒░▓█ ░██ ▒▓█  ▄ ▒▓▓▄ ▄██▒▓██ █▄ ▒▓█  ▄ ▒██▀▀█▄  
▒██░   ▓██░ ▓█   ▓██▒▒██▒   ░██▒░▒████▒   ▒ ▓███▀ ░░▓█▒░██▓░▒████▒▒ ▓███▀ ░▒██▒ █▄░▒████▒░██▓ ▒██▒
░ ▒░   ▒ ▒  ▒▒   ▓▒█░░ ▒░   ░  ░░░ ▒░ ░   ░ ░▒ ▒  ░ ▒ ░░▒░▒░░ ▒░ ░░ ░▒ ▒  ░▒ ▒▒ ▓▒░░ ▒░ ░░ ▒▓ ░▒▓░
░ ░░   ░ ▒░  ▒   ▒▒ ░░  ░      ░ ░ ░  ░     ░  ▒    ▒ ░▒░ ░ ░ ░  ░  ░  ▒   ░ ░▒ ▒░ ░ ░  ░  ░▒ ░ ▒░
   ░   ░ ░   ░   ▒   ░      ░      ░      ░         ░  ░░ ░   ░   ░        ░ ░░ ░    ░     ░░   ░ 
         ░       ░  ░       ░      ░  ░   ░ ░       ░  ░  ░   ░  ░░ ░      ░  ░      ░  ░   ░     
                                          ░                       ░                               
                                          """

print(art)


def pseudo_entré():
    return input("Name : ")
    

pseudo_a_verifier = pseudo_entré()

disponibles = []

for lien in liens:
    disponible = verifier_disponibilite_pseudo(lien, pseudo_a_verifier)
    if disponible:
        disponibles.append(disponible)

if disponibles:
    print(f"Le pseudo '{pseudo_a_verifier}' est libre sur les sites suivants :")
    for site in disponibles:
        print(site)
else:
    print(f"Le pseudo '{pseudo_a_verifier}' n'est pas libre sur ces sites.")
