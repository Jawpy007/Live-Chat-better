Video Overlay Sync

> **Partagez des vidéos synchronisées en overlay avec vos amis en temps réel**

Une application complète permettant d'afficher des vidéos en overlay transparent synchronisé entre plusieurs utilisateurs. Parfait pour regarder des vidéos ensemble pendant vos sessions de jeu ou de stream !

---

Fonctionnalités

Client Desktop (PyQt5)
- **Overlay transparent** : Fenêtre invisible en attente, visible uniquement pendant la lecture
- **Click-through** : Cliquez à travers l'overlay sans gêner vos applications
- **Redimensionnement adaptatif** : S'adapte automatiquement à la taille de chaque vidéo
- **System tray** : Contrôlez l'application depuis la barre des tâches
- **Interface de configuration** : Design dark mode moderne type Notion
- **Multi-rooms** : Rejoignez différentes salles avec vos groupes d'amis

Interface Web
- **Upload de vidéos** : Glissez-déposez vos vidéos (MP4, AVI, MOV, MKV, WEBM)
- **URLs externes** : Ajoutez des liens directs vers des vidéos
- **Contrôles en temps réel** :
  - ⏭️ Skip la vidéo en cours
  - 🗑️ Vider toute la file d'attente
- **File d'attente live** : Visualisez les vidéos en attente en temps réel
- **Statistiques** : Suivez l'utilisation du serveur (salles, vidéos, stockage)

Serveur
- **WebSocket temps réel** : Synchronisation instantanée entre tous les clients
- **Upload et streaming HTTP** : Gestion efficace des fichiers vidéo
- **Nettoyage automatique** : Suppression des vidéos après lecture (économise l'espace disque)
- **Multi-salles** : Support de plusieurs groupes simultanés
- **API REST** : Endpoints pour contrôler les salles à distance

---

Installation

Prérequis
- **Python 3.8+**
- **Windows** (pour le client desktop avec overlay)
- **Navigateur web moderne** (pour l'interface web)

1. Cloner le repository
```bash
git clone https://github.com/votre-username/video-overlay-sync.git
cd video-overlay-sync
```

2. Installer les dépendances
```bash
pip install -r requirements.txt
```

3. Structure des fichiers
```
video-overlay-sync/
├── app.py                      # Serveur Flask + WebSocket
├── overlay_launcher.py         # Client desktop avec GUI
├── requirements.txt            # Dépendances Python
├── templates/
│   └── index.html             # Interface web
└── uploads/                   # Dossier des vidéos (auto-créé)
```

---

 Utilisation

Démarrer le serveur

```bash
python app.py
```

Le serveur démarre sur :
- Interface web : `http://localhost:5000`
- WebSocket : `ws://localhost:8765`


Lancer le client desktop

```bash
python overlay_launcher.py
```

1. **Configurer la connexion** :
   - Serveur WebSocket : `ws://localhost:8765` (ou IP du serveur)
   - ID de la salle : Nom unique pour votre groupe
   - Taille max : Dimensions maximales de l'overlay

2. **Cliquer sur "Start Overlay"**
3. L'overlay se lance et se connecte automatiquement
4. **System tray** : L'icône apparaît dans la barre des tâches
   - 🟢 Vert : Connecté
   - 🔵 Bleu : Lecture en cours
   - 🔴 Rouge : Erreur
   - Double-clic : Rouvrir la configuration

Utiliser l'interface web

1. Ouvrir `http://localhost:5000` (ou `http://IP_SERVEUR:5000`)
2. **Se connecter** :
   - ID de la salle : Même nom que les clients desktop
   - Votre nom : Identifiez-vous
3. **Uploader des vidéos** :
   - Glissez-déposez un fichier
   - Ou cliquez pour parcourir
4. **Ajouter des URLs** : Collez un lien direct vers une vidéo
5. **Contrôler la lecture** :
   - Skip : Passer à la vidéo suivante
   - Clear : Vider toute la queue

---

Utilisation en réseau (serveur distant)

Configuration du serveur

1. **Sur votre serveur Linux/Windows** :
   ```bash
   python app.py
   ```

2. **Ouvrir les ports** :
   - Port `5000` : Interface web (TCP)
   - Port `8765` : WebSocket (TCP)

   **Ubuntu/Debian** :
   ```bash
   sudo ufw allow 5000/tcp
   sudo ufw allow 8765/tcp
   ```

3. **Trouver l'IP du serveur** :
   ```bash
   ip addr show  # Linux
   ipconfig      # Windows
   ```
Configuration des clients

**Client desktop** :
- Serveur WebSocket : `ws://VOTRE_IP:8765`

**Interface web** :
- Ouvrir : `http://VOTRE_IP:5000`
- La connexion WebSocket se fait automatiquement

---

Captures d'écran

Interface de configuration
Interface pour configurer la connexion et la taille de l'overlay.

Interface web
Panel de contrôle complet avec upload, file d'attente et statistiques en temps réel.

Overlay en action
Fenêtre transparente qui s'affiche automatiquement pendant la lecture des vidéos.

---

Configuration avancée

Modifier la taille max des vidéos
Dans `app.py` :
```python
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB (modifiable)
```

Changer le délai de nettoyage
Dans `app.py` :
```python
if time.time() - info.get('last_used', info['upload_time']) > 30:  # 30 secondes
```

Formats vidéo supportés
```python
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv'}
```

---

API REST

Endpoints disponibles

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/` | Interface web |
| `POST` | `/api/upload` | Upload une vidéo |
| `POST` | `/api/add_url` | Ajouter une URL |
| `POST` | `/api/rooms/{room_id}/skip` | Skip la vidéo actuelle |
| `POST` | `/api/rooms/{room_id}/clear` | Vider la queue |
| `GET` | `/api/rooms/{room_id}/queue` | Récupérer la queue |
| `GET` | `/api/stats` | Statistiques du serveur |

Exemple d'utilisation

**Skip une vidéo** :
```bash
curl -X POST http://localhost:5000/api/rooms/test/skip
```

**Statistiques** :
```bash
curl http://localhost:5000/api/stats
```

---

Un probleme ? :

Le client ne se connecte pas
- ✅ Vérifiez que le serveur est démarré
- ✅ Vérifiez l'URL WebSocket (doit commencer par `ws://`)
- ✅ Vérifiez les pare-feu (ports 5000 et 8765)
- ✅ Sur Windows, autorisez Python dans le pare-feu

Les vidéos ne se chargent pas
- ✅ Vérifiez le format (MP4 recommandé)
- ✅ Vérifiez la taille (max 500 MB par défaut)
- ✅ Vérifiez les permissions du dossier `uploads/`

L'overlay n'est pas transparent
- ✅ Windows uniquement pour le click-through
- ✅ Vérifiez que `pywin32` est installé
- ✅ L'overlay devient visible uniquement pendant la lecture

Les vidéos restent dans la queue
- ✅ Assurez-vous que le client desktop est bien connecté
- ✅ Le client envoie un signal au serveur quand la vidéo se termine
- ✅ Utilisez le bouton "Clear" pour vider manuellement

---

Roadmap

v2.0 (À venir)
- [ ] Support YouTube avec yt-dlp
- [ ] Contrôle du volume depuis le web
- [ ] Pause/Play synchronisé
- [ ] Chat intégré
- [ ] Authentification utilisateurs
- [ ] Support multi-plateformes (Linux/macOS)
- [ ] Mode Picture-in-Picture
- [ ] Playlists sauvegardées

---

Contributing

Les contributions sont les bienvenues ! N'hésitez pas à :
1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit vos changements (`git commit -m 'Add amazing feature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

---


## 👨‍💻 Auteurs

- **Jawpy** - 

---

Sources utilisées

- [PyQt5](https://riverbankcomputing.com/software/pyqt/) - Interface graphique
- [Flask](https://flask.palletsprojects.com/) - Serveur web
- [websockets](https://websockets.readthedocs.io/) - Communication temps réel
- Inspiré par les besoins des gamers et streamers

---

<p align="center">
  Fait avec ❤️ pour la communauté
</p>

<p align="center">
  ⭐ N'oubliez pas de star le projet si vous l'aimez !
</p>
