# Wine Explorer · application mobile

Application native iPhone et Android (Expo SDK 58, React Native, Expo Router), branchée sur
l'API Django du site (`/api/v1/`). Une seule base de données : celle du site.

```
src/
  app/                  écrans (Expo Router) : un fichier = un écran
    (tabs)/             Aujourd'hui · Blind test · Chaud-froid · Classement · Profil (onglets natifs)
    game/[id].tsx       partie de blind test
    wine/[slug].tsx     fiche d'un vin
    player/[username]   profil public d'un joueur
    auth.tsx            connexion, inscription, suppression du compte (fenêtre modale)
  api/                  client HTTP et types des réponses
  components/           éléments d'interface communs
  theme.ts              charte : couleurs, typographies (Fraunces, Inter), espacements
  i18n.ts               textes de l'interface en français et en anglais
```

## Tester sur son téléphone (5 minutes)

Il faut le PC et le téléphone **sur le même Wi-Fi**.

1. **Installer Expo Go** sur le téléphone (App Store ou Google Play).
2. **Lancer le site Django**, en écoutant sur le réseau local (et pas seulement sur le PC) :
   ```bash
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py runserver 0.0.0.0:8000
   ```
   Sous Windows, accepter la fenêtre du pare-feu (réseaux privés).
3. **Lancer l'appli**, dans un second terminal :
   ```bash
   cd mobile
   npm install
   npx expo start
   ```
4. **Scanner le QR code** affiché : avec l'appareil photo sur iPhone, depuis Expo Go sur Android.

L'appli trouve seule le serveur : c'est le PC qui a lancé `npx expo start`, port 8000.
Chaque fichier enregistré se recharge instantanément sur le téléphone.

### Si l'appli affiche « Serveur injoignable »

- Vérifier que `runserver` écoute bien sur `0.0.0.0:8000` (et pas `127.0.0.1`).
- Ouvrir `http://<IP du PC>:8000/api/v1/today/` dans le navigateur du téléphone : on doit voir du JSON.
  L'IP s'obtient avec `ipconfig` (Windows), ligne « Adresse IPv4 ».
- Un Wi-Fi d'entreprise ou d'hôtel isole souvent les appareils : utiliser le partage de connexion du téléphone.
- Pour viser un autre serveur : copier `.env.example` en `.env` et renseigner `EXPO_PUBLIC_API_URL`.

## Vérifications

```bash
npx tsc --noEmit     # typage
npx expo lint        # lint
```

## Distribuer à des amis (Android, sans store)

Le serveur en ligne est `https://wine-explorer.up.railway.app` ; les builds `preview` et
`production` (`eas.json`) pointent dessus.

```bash
npm install
npx eas-cli@latest login                 # compte gratuit sur expo.dev
npm run build:android                    # APK compilé dans le cloud (~15 min)
```

À la fin, EAS affiche un lien et un QR code : les amis l'ouvrent sur leur téléphone Android,
téléchargent l'APK et l'installent (autoriser « sources inconnues » si Android le demande).
Le premier `eas build` propose de créer le projet sur expo.dev : répondre oui.

## Tester avec Expo Go contre le serveur en ligne

Pas besoin de lancer Django : créer `mobile/.env` avec
`EXPO_PUBLIC_API_URL=https://wine-explorer.up.railway.app/api/v1`, puis `npx expo start`.

## Publier sur les stores

Les builds se font dans le cloud avec EAS (pas besoin de Mac) :

```bash
npx eas-cli@latest login
npx eas-cli@latest build --profile preview --platform android   # APK à installer directement
npx eas-cli@latest build --profile production                     # builds pour les stores
npx eas-cli@latest submit
```

Avant : mettre le site en ligne en HTTPS, renseigner `EXPO_PUBLIC_API_URL`, et vérifier les
identifiants `com.grudal.wineexplorer` dans `app.json`.

## Choix de conception

- **Onglets et en-têtes natifs** (barre d'onglets système, grands titres iOS) : l'appli se comporte
  comme une appli du téléphone, pas comme un site.
- **Charte du site** : papier `#F8F8F4`, encre `#23262F`, grenat `#7A1F3D` ; vert olive pour
  « trouvé », ocre pour « proche ». Titres et chiffres en Fraunces, texte en Inter.
- **Jouer sans compte** : l'appareil reçoit un identifiant ; ses parties rejoignent le compte à la
  connexion. Le classement demande un compte.
- **Retour haptique** sur chaque essai, **partage** du résultat sans dévoiler le vin.
- **Le vin mystère ne quitte jamais le serveur** avant la fin de la partie.
- **Suppression du compte** dans l'appli (exigée par Apple et Google).
