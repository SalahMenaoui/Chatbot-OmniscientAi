# Workflow: deliver_chatbot

## Nouveau workflow (Admin Web)

Depuis la refonte en SaaS, tout se fait depuis l'interface admin en ligne.
Plus besoin de passer par le CLI ou des fichiers locaux.

---

## Créer un nouveau client

1. Va sur `/admin/setup` → "Nouveau client" → entre nom + clé (ex: `aqua-services`)
2. Tu arrives directement sur la page **Config** du client

## Configurer le chatbot (page Config)

1. **Sources** — colle les URLs :
   - Site web (obligatoire)
   - Instagram (optionnel — scrape bio, captions, avatar)
   - Google Maps (optionnel — nécessite `GOOGLE_PLACES_API_KEY`)
2. Clique **⚡ Analyser toutes les sources** — 20-40 sec
3. Le formulaire se pré-remplit : nom du bot, system prompt, couleurs, polices, avatar
4. Ajuste si besoin → **Sauvegarder →**

## Livrer au client

Le chatbot est immédiatement live à :
```
https://web-production-42cf20.up.railway.app/clients/<client_key>/chatbot/
```

Pour l'intégrer sur le site du client, donne-lui cette ligne :
```html
<script src="https://web-production-42cf20.up.railway.app/static/widget.js"
        data-client="<client_key>"></script>
```
(disponible aussi via le bouton **⟨/⟩ Intégrer** dans la liste clients)

## Tiers

| Tier | Ce que le client a |
|------|-------------------|
| 1    | Chatbot uniquement |
| 2    | + Dashboard conversations + capture leads |
| 3    | + Emails automatiques (relance) |

Upgrade/downgrade depuis `/admin/clients` — instantané, aucun redéploiement.

## Créer un accès dashboard (Tier 2+)

Dans `/admin/clients` → bouton **+ Accès dashboard** → email + mot de passe.
Le client se connecte sur `/dashboard/login`.

---

## Pipeline

```
Admin UI → Analyser sources → Sauvegarder config → Chatbot live
```

Aucun git push nécessaire. La config est stockée en base et servie dynamiquement.
