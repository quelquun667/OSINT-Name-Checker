import requests
import sys
import time
from colorama import init, Fore, Style
import os

pasvoulu1 = '"'
pasvoulu2 = "', :`@!"
pasvoulu = pasvoulu1 + pasvoulu2


try:
    import requests
    from colorama import init, Fore, Style
    print("Everything needed is loaded")
    time.sleep(2)
except ImportError:
    print("Installation of requirements")
    time.sleep(1)
    os.system('pip install requests')
    os.system('pip install colorama')

    # Redémarre le script pour charger les librairies installées
    os.system('python script.py ' + ' '.join(sys.argv[1:]))
    sys.exit()

# Efface la console (cmd)
os.system('cls' if os.name == 'nt' else 'clear')


# Initialisation de colorama
init(autoreset=True)

def verif(url, pseudo):
    not_available_phrases = {
        "this page is unfortunately not available",
        "This account cannot be found",
    }
    
    try:
        response = requests.get(url + pseudo)
        texterror = response.text.lower()
        if response.status_code == 404:
            print(f"{Fore.RED}(-) {url.split('//')[-1].split('/')[0]}{Style.RESET_ALL}")
            return url.split('//')[-1].split('/')[0]
        elif any(phrase in texterror for phrase in not_available_phrases):
            print(f"{Fore.RED}(-) {url.split('//')[-1].split('/')[0]}{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}(+) {url.split('//')[-1].split('/')[0]}{Style.RESET_ALL}")
    except requests.RequestException as e:
        print(f"{Fore.YELLOW}(~){url.split('//')[-1].split('/')[0]}{Style.RESET_ALL}")

# Exemple d'utilisation avec des liens
liens = [
    "https://www.instagram.com/",
    "https://www.tiktok.com/@",
    "https://www.github.com/",
    "https://www.facebook.com/",
    "https://www.threads.net/@",
    "https://www.pinterest.fr/",
    "https://twitter.com/",
    "https://www.reddit.com/user/",
    # Ajoutez d'autres liens ici
]

art = f"""{Fore.MAGENTA}███▄    █  ▄▄▄       ███▄ ▄███▓▓█████     ▄████▄   ██░ ██ ▓█████  ▄████▄   ██ ▄█▀▓█████  ██▀███
 ██ ▀█   █ ▒████▄    ▓██▒▀█▀ ██▒▓█   ▀    ▒██▀ ▀█  ▓██░ ██▒▓█   ▀ ▒██▀ ▀█   ██▄█▒ ▓█   ▀ ▓██ ▒ ██▒
▓██  ▀█ ██▒▒██  ▀█▄  ▓██    ▓██░▒███      ▒▓█    ▄ ▒██▀▀██░▒███   ▒▓█    ▄ ▓███▄░ ▒███   ▓██ ░▄█ ▒
▓██▒  ▐▌██▒░██▄▄▄▄██ ▒██    ▒██ ▒▓█  ▄    ▒▓▓▄ ▄██▒░▓█ ░██ ▒▓█  ▄ ▒▓▓▄ ▄██▒▓██ █▄ ▒▓█  ▄ ▒██▀▀█▄  
▒██░   ▓██░ ▓█   ▓██▒▒██▒   ░██▒░▒████▒   ▒ ▓███▀ ░░▓█▒░██▓░▒████▒▒ ▓███▀ ░▒██▒ █▄░▒████▒░██▓ ▒██▒
░ ▒░   ▒ ▒  ▒▒   ▓▒█░░ ▒░   ░  ░░░ ▒░ ░   ░ ░▒ ▒  ░ ▒ ░░▒░▒░░ ▒░ ░░ ░▒ ▒  ░▒ ▒▒ ▓▒░░ ▒░ ░░ ▒▓ ░▒▓░
░ ░░   ░ ▒░  ▒   ▒▒ ░░  ░      ░ ░ ░  ░     ░  ▒    ▒ ░▒░ ░ ░ ░  ░  ░  ▒   ░ ░▒ ▒░ ░ ░  ░  ░▒ ░ ▒░
   ░   ░ ░   ░   ▒   ░      ░      ░      ░         ░  ░░ ░   ░   ░        ░ ░░ ░    ░     ░░   ░ 
         ░       ░  ░       ░      ░  ░   ░ ░       ░  ░  ░   ░  ░░ ░      ░  ░      ░  ░   ░     
                                          ░                       ░                               """

print(art)
print(f"{Fore.MAGENTA}By Quelqu'un \n\n")


def pseudo_entré():
    return input("Name : ")
    
while True:
    
    pseudo_a_verifier = pseudo_entré()

    disponibles = []



    if any(c in pasvoulu for c in pseudo_a_verifier):
        print("Error : The name contains unwanted characters")
        time.sleep(0.5)
    else:
        break

for lien in liens:
    disponible = verif(lien, pseudo_a_verifier)
    if disponible:
        disponibles.append(disponible)
print(f"\n\n{Fore.GREEN}(+) Name used")
print(f"{Fore.RED}(-) Name not used")
print(f"{Fore.YELLOW}(~) Connection Error")