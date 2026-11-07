// French. Menu names follow what WhatsApp, Android and Apple show in French.
import { Code } from "@/components/code"

import type { Messages } from "./en"

// French uses the singular for 0 and 1.
const one = (n: string) => n === "0" || n === "1"

export const fr: Messages = {
  header: {
    tagline: "Reste sur cet ordinateur · n'écrit sur un téléphone qu'à la fin, quand vous le décidez",
    language: "Langue",
    theme: "Thème",
    light: "Clair",
    dark: "Sombre",
    system: "Système",
  },
  steps: {
    start: "Début",
    android: "Android",
    before: "iPhone",
    account: "Compte",
    after: "Comparer",
    convert: "Convertir",
    write: "Écrire",
    restore: "Restaurer",
    copy: "Copier",
    done: "Résultats",
  },
  stepOf: (n, total) => `Étape ${n} sur ${total}`,
  stepLabel: (n, title, done) => `Étape ${n} : ${title}${done ? " (terminée)" : ""}`,
  stepSkipped: "inutile",
  nav: { back: "Retour", continue: "Continuer", start: "Commencer", first: (step) => `D'abord : ${step}` },
  common: {
    loading: "Chargement…",
    openWithLink: "Ouvrez l'assistant avec le lien affiché par `whatferry ui`.",
    cantReach: (m) => `Impossible de joindre whatferry : ${m}. \`whatferry ui\` est-il toujours lancé ?`,
    failed: "Ça n'a pas marché",
    checked: "Vérifié",
    searchAgain: "Rechercher à nouveau",
    messagesRange: (a, b) => (
      <>
        Messages du <strong>{a}</strong> au <strong>{b}</strong>.
      </>
    ),
    noMessages: "Pas encore de messages.",
  },
  counts: {
    chats: "discussions",
    messages: "messages",
    media: "médias",
    "quoted replies": "réponses citées",
    "reactions and other add-ons": "réactions et autres ajouts",
    "contact cards": "fiches contact",
    locations: "positions",
    calls: "appels",
    "contacts and groups (jid)": "contacts et groupes (jid)",
    "group members": "membres de groupes",
    "group info": "infos de groupes",
    "message info (receipts)": "infos de messages (accusés de réception)",
    "profile push names": "noms de profil",
    "files added": "fichiers ajoutés",
    "files changed": "fichiers modifiés",
    "files removed": "fichiers supprimés",
    "chats matched": "discussions déjà présentes",
    "chats created": "discussions ajoutées",
    "media placed": "fichiers médias placés",
    "media missing": "fichiers médias introuvables",
  },
  start: {
    title: "Transférez vos discussions WhatsApp d'Android vers l'iPhone",
    titleToAndroid: "Transférez vos discussions WhatsApp de l'iPhone vers Android",
    lead: "Cet assistant transfère les discussions d'un compte WhatsApp Android vers WhatsApp sur votre iPhone, sans effacer l'iPhone. Vos sauvegardes sont seulement lues ; l'iPhone n'est modifié qu'une fois, à la fin, quand vous choisissez de restaurer.",
    leadToAndroid: "Cet assistant transfère les discussions d'un compte WhatsApp iPhone vers WhatsApp sur votre téléphone Android. Vos sauvegardes sont seulement lues ; le téléphone Android n'est modifié qu'une fois, à la fin, quand vous y copiez la nouvelle sauvegarde.",
    directionTitle: "Dans quel sens",
    android: "Android",
    iphone: "iPhone",
    directionNote: {
      "to-iphone": "Vers WhatsApp sur un iPhone déjà configuré, comme deuxième compte ou comme seul compte.",
      "to-android": "Vers WhatsApp sur un téléphone Android, via la restauration de sauvegarde de WhatsApp lui-même.",
    },
    needsToAndroid: [
      "L'iPhone, avec WhatsApp et les discussions à transférer.",
      "Le téléphone Android, avec WhatsApp connecté au numéro que vous transférez.",
      "Un câble pour chaque téléphone, et le débogage USB activé sur le téléphone Android.",
      "Environ une heure, surtout à attendre les sauvegardes. Vous pouvez fermer et revenir : la progression est enregistrée.",
    ],
    happensToAndroid: [
      "Sauvegardez l'iPhone, pour que l'assistant puisse lire les discussions, photos et vidéos du compte.",
      "Faites la sauvegarde chiffrée de WhatsApp sur le téléphone Android, avec une clé à 64 chiffres, et apportez le fichier ici.",
      "Convertissez les discussions de l'iPhone dans cette sauvegarde et parcourez un aperçu du résultat.",
      "Écrivez la nouvelle sauvegarde, copiez-la sur le téléphone Android et restaurez-la dans WhatsApp avec la clé.",
    ],
    needTitle: "Il vous faut",
    needs: [
      "Le téléphone Android, avec WhatsApp et les discussions à transférer.",
      "L'iPhone, avec WhatsApp déjà configuré pour son propre numéro.",
      "Un câble pour connecter l'iPhone à cet ordinateur.",
      "Environ une heure, surtout à attendre les sauvegardes. Vous pouvez fermer et revenir : la progression est enregistrée.",
    ],
    happensTitle: "Ce qui se passe",
    happens: [
      "Faites une sauvegarde WhatsApp chiffrée sur le téléphone Android et apportez le fichier ici.",
      "Sauvegardez l'iPhone, pour que l'assistant voie comment WhatsApp stocke votre compte actuel.",
      "Ajoutez le numéro Android à WhatsApp sur l'iPhone comme deuxième compte.",
      "Sauvegardez à nouveau l'iPhone. La comparaison des deux sauvegardes montre exactement où iront les discussions du nouveau compte.",
      "Convertissez les discussions Android et parcourez un aperçu du résultat.",
      "Écrivez une nouvelle copie de la sauvegarde de l'iPhone contenant les discussions, puis restaurez-la sur l'iPhone.",
    ],
    privateTitle: "Ce qui reste privé",
    privateLead: "Rien ne quitte cet ordinateur.",
    private: (home) => [
      "La page ne communique qu'avec whatferry sur cet ordinateur. Rien n'est envoyé nulle part.",
      "Les clés et mots de passe sont utilisés une fois et jamais enregistrés.",
      <>
        Les copies déchiffrées sont conservées dans <Code>{home}</Code>, lisibles par vous seul. Supprimez-les quand vous
        avez terminé.
      </>,
    ],
  },
  android: {
    title: "Sauvegarde Android",
    lead: "La sauvegarde chiffrée de WhatsApp, avec une clé à 64 chiffres que vous notez, peut être lue ici sans rooter le téléphone.",
    makeTitle: "Faites la sauvegarde sur le téléphone Android",
    make: [
      "Ouvrez WhatsApp → Paramètres → Discussions → Sauvegarde des discussions → Sauvegarde chiffrée de bout en bout → Activer.",
      "Choisissez « Utiliser plutôt une clé de chiffrement à 64 chiffres », puis générez la clé. Notez-la ou faites une capture d'écran : WhatsApp ne peut pas l'afficher à nouveau.",
      "De retour dans Sauvegarde des discussions, appuyez sur Sauvegarder. Un fichier est ainsi enregistré sur le téléphone même si les sauvegardes Google Drive sont désactivées.",
    ],
    toAndroidTitle: "D'abord, WhatsApp sur le téléphone Android",
    toAndroidBody: "Installez WhatsApp et connectez-vous avec le numéro que vous transférez. S'il propose de restaurer une sauvegarde, passez. Faites ensuite la sauvegarde ci-dessous : elle donne à l'assistant la base de données vide de WhatsApp pour le compte, dans laquelle vont les discussions de l'iPhone.",
    multiTitle: "Plusieurs comptes WhatsApp sur le téléphone ?",
    multiBody: "Chaque compte a sa propre sauvegarde et sa propre clé. Passez au compte à transférer (appuyez sur votre photo de profil → changer de compte) avant les étapes ci-dessus, et répétez-les pour chaque compte voulu.",
    bringTitle: "Apportez le fichier sur cet ordinateur",
    bringLead: "N'importe laquelle de ces méthodes fonctionne ; prenez la plus simple.",
    tabs: { share: "Partager depuis le téléphone", cable: "Transfert de fichiers USB", adb: "Copier avec le débogage USB" },
    share: [
      <>
        Ouvrez l'application de fichiers du téléphone (Files de Google, ou Mes fichiers sur Samsung) et allez dans{" "}
        <Code>Android/media/com.whatsapp/WhatsApp</Code>. Certaines applications de fichiers masquent le dossier{" "}
        <Code>Android</Code> ; Files de Google l'affiche.
      </>,
      <>
        Ouvrez <Code>Databases</Code>, ou avec plusieurs comptes <Code>accounts</Code> → le numéro du compte →{" "}
        <Code>Databases</Code>.
      </>,
      <>
        Appuyez de manière prolongée sur <Code>msgstore.db.crypt15</Code> (celui sans date) et appuyez sur Partager.
      </>,
      "Envoyez-le sur cet ordinateur avec ce que vous avez : LocalSend (gratuit, téléphone et ordinateur sur le même Wi-Fi, rien ne passe par internet), Quick Share (Windows), Google Drive, ou un e-mail ou un message à vous-même.",
      "Enregistrez-le dans Téléchargements, puis cliquez sur Rechercher à nouveau ci-dessous.",
    ],
    cable: (platform) => [
      "Branchez le téléphone sur cet ordinateur avec un câble USB et déverrouillez-le.",
      "Sur le téléphone, appuyez sur la notification « Recharge de cet appareil via USB » et choisissez Transfert de fichiers.",
      {
        darwin: "Un Mac ne sait pas ouvrir seul les téléphones Android : installez OpenMTP (gratuit, openmtp.ganeshrvel.com) et ouvrez-y le téléphone.",
        win32: "Ouvrez l'Explorateur de fichiers : le téléphone apparaît sous Ce PC.",
        other: "Votre gestionnaire de fichiers affiche le téléphone dans sa barre latérale.",
      }[platform],
      "Copiez msgstore.db.crypt15 du dossier ci-dessous vers Téléchargements, puis cliquez sur Rechercher à nouveau ci-dessous.",
    ],
    foldersTitle: "Où WhatsApp range les sauvegardes sur le téléphone",
    folders: ["Un compte", "Plusieurs comptes", "WhatsApp Business", "Android 10 ou antérieur"],
    foldersNote: (
      <>
        Avec plusieurs comptes, chaque dossier <Code>accounts/&lt;numéro&gt;</Code> correspond à un compte : choisissez
        celui dont le msgstore.db.crypt15 est le plus récent, juste après avoir appuyé sur Sauvegarder. Les fichiers se
        terminant par .crypt14 et les fichiers datés ou « increment » ne sont pas utilisables.
      </>
    ),
    chooseTitle: "Choisissez le fichier",
    searching: "Recherche…",
    noneFound: "Aucune sauvegarde WhatsApp trouvée pour l'instant.",
    chooseFile: "Choisir un fichier…",
    copyingFile: (name) => `Copie de ${name}…`,
    searchHint: (folders) => (
      <>Rechercher à nouveau cherche des sauvegardes WhatsApp dans {folders}. Ailleurs ? Utilisez Choisir un fichier.</>
    ),
    listAnd: " et ",
    listSep: ", ",
    keyTitle: "Saisissez la clé",
    keyLabel: "Clé à 64 chiffres",
    keyPlaceholder: "64 caractères, les espaces sont acceptés",
    showKey: "Afficher la clé",
    hideKey: "Masquer la clé",
    keyHint: "Utilisée une fois pour déchiffrer, puis oubliée. Inutile si vous avez choisi un msgstore.db déjà déchiffré.",
    decrypting: "Déchiffrement et vérification de la sauvegarde…",
    decrypt: "Déchiffrer et vérifier",
    checkAgain: "Vérifier à nouveau",
    resultLine: (version, db, checked) => `WhatsApp ${version} · version de base de données ${db} · vérifiée ${checked}`,
    legacy: "Cette sauvegarde utilise l'ancien format de WhatsApp. Mettez à jour WhatsApp sur le téléphone et sauvegardez à nouveau.",
    jidTitle: "Identifiants de contact par type",
    jidHead: ["Serveur", "Nombre"],
    decryptedCopy: "Copie déchiffrée :",
    accountsTitle: "Comptes Android",
    accountsLead: "Chaque compte est transféré séparément. Pour en ajouter un autre, choisissez son fichier de sauvegarde ci-dessous et déchiffrez-le ; passez de l'un à l'autre ici.",
    accountRow: (ends, messages) => `Numéro se terminant par ${ends ?? "?"} · ${messages} messages`,
    accountProgress: (destination, secondDone) =>
      [destination ? `va vers : ${destination}` : "destination pas encore choisie", secondDone ? "deuxième sauvegarde vérifiée" : null]
        .filter(Boolean).join(" · "),
    destinationNames: { setup: "configurer WhatsApp", second: "deuxième compte", existing: "compte existant" },
    workingOn: "Compte en cours",
    switchTo: "Passer à ce compte",
    movingAccount: (ends) => `Compte Android se terminant par ${ends ?? "?"}`,
  },
  phone: {
    intro: (folder) => (
      <>
        Branchez le téléphone sur cet ordinateur et whatferry copie lui-même la sauvegarde, directement dans{" "}
        <Code>{folder}</Code>. Il faut le débogage USB sur le téléphone et adb sur cet ordinateur ; vous pourrez
        désactiver le débogage ensuite.
      </>
    ),
    looking: "Recherche d'adb et des téléphones connectés…",
    noAdbTitle: "adb n'est pas installé sur cet ordinateur",
    noAdbIntro: "adb est l'outil gratuit de Google pour communiquer avec les téléphones Android en USB.",
    install: {
      darwin: ["Avec Homebrew : brew install --cask android-platform-tools", "Ou téléchargez platform-tools chez Google (ci-dessous) et décompressez-le."],
      win32: ["Dans un terminal : winget install Google.PlatformTools", "Ou téléchargez platform-tools chez Google (ci-dessous) et décompressez-le."],
      other: ["Debian ou Ubuntu : sudo apt install adb · Fedora : sudo dnf install android-tools", "Ou téléchargez platform-tools chez Google (ci-dessous) et décompressez-le."],
    },
    download: (
      <>
        Téléchargement Google : <Code>developer.android.com/tools/releases/platform-tools</Code>. Si adb se trouve là où
        whatferry ne cherche pas, lancez-le avec <Code>WHATFERRY_ADB=/path/to/adb</Code>.
      </>
    ),
    debugTitle: "Activez le débogage USB",
    debug: [
      "Sur le téléphone, ouvrez Paramètres → À propos du téléphone et appuyez sept fois sur Numéro de build. Saisissez votre code si demandé ; le message « Vous êtes maintenant développeur » s'affiche. (Samsung : Paramètres → À propos du téléphone → Informations sur le logiciel → Numéro de version.)",
      "Revenez dans Paramètres → Système → Options pour les développeurs et activez Débogage USB.",
      "Branchez le téléphone sur cet ordinateur avec un câble USB et déverrouillez-le.",
      "Appuyez sur Autoriser dans « Autoriser le débogage USB ? ». Cocher « Toujours autoriser sur cet ordinateur » évite de le refaire.",
      "Cliquez sur Trouver le téléphone ci-dessous.",
    ],
    debugOff: "Quand vous avez terminé : Options pour les développeurs → désactivez Débogage USB.",
    notReady: (model) => `${model} n'est pas prêt`,
    advice: {
      unauthorized: "Déverrouillez le téléphone et appuyez sur Autoriser dans « Autoriser le débogage USB ? ».",
      offline: "Le téléphone ne répond pas : débranchez-le, rebranchez-le et déverrouillez-le.",
      "no permissions": "Cet ordinateur n'a pas le droit de communiquer avec le téléphone (sous Linux, ajoutez une règle udev pour Android).",
      authorizing: "En attente de votre appui sur Autoriser sur le téléphone.",
    },
    otherState: (state) => `adb indique « ${state} ».`,
    phone: "Téléphone Android",
    connected: "Connecté",
    account: (app, account) => (account ? `${app} · compte ${account}` : app),
    noBackups: "Pas encore de sauvegarde WhatsApp sur ce téléphone. Faites-en une d'abord (étape 1), puis cliquez à nouveau sur Trouver le téléphone.",
    noUsable: "Pas encore de sauvegarde utilisable : activez la sauvegarde chiffrée avec clé à 64 chiffres et appuyez sur Sauvegarder (étape 1), puis cliquez à nouveau sur Trouver le téléphone.",
    otherFiles: (n) => (n <= 1 ? `${n} autre fichier inutilisable` : `${n} autres fichiers inutilisables`),
    notes: {
      rooted: "Ancien chiffrement : sa clé n'existe que sur un téléphone rooté. Activez la sauvegarde chiffrée avec clé à 64 chiffres et sauvegardez à nouveau pour obtenir un fichier .crypt15.",
      increment: "Une sauvegarde partielle (incrémentielle) ; utilisez le fichier msgstore complet.",
      other: "Ce n'est pas une sauvegarde de discussions WhatsApp.",
    },
    copy: "Copier",
    copying: "Copie…",
    copiedTitle: (name) => `${name} copié`,
    copiedBody: "Il est sélectionné ci-dessous, à l'étape 3.",
    findPhone: "Trouver le téléphone",
  },
  backup: {
    title: { before: "Sauvegarde de l'iPhone", after: "Deuxième sauvegarde de l'iPhone" },
    lead: {
      before: "Une sauvegarde montre comment WhatsApp stocke actuellement ses données sur l'iPhone. L'assistant la lit ; il ne la modifie jamais.",
      after: "Une fois le deuxième compte ajouté, une nouvelle sauvegarde montre quels fichiers le nouveau compte a créés. C'est là qu'iront les discussions Android.",
    },
    needFirst: "Vérifiez d'abord la première sauvegarde de l'iPhone.",
    goFirst: "Aller à la première sauvegarde",
    makeTitle: { before: "Sauvegardez l'iPhone", after: "Sauvegardez à nouveau l'iPhone" },
    make: {
      darwin: [
        "Connectez l'iPhone à ce Mac avec un câble et déverrouillez-le. Touchez Se fier si on vous le demande.",
        "Ouvrez le Finder et sélectionnez l'iPhone dans la barre latérale.",
        "Sous Sauvegardes, choisissez « Sauvegarder toutes les données de votre iPhone sur ce Mac ».",
        "Cochez « Chiffrer la sauvegarde locale » et choisissez un mot de passe dont vous vous souviendrez. Vous le saisirez ici dans un instant.",
        "Cliquez sur Sauvegarder maintenant et attendez la fin.",
      ],
      win32: [
        "Connectez l'iPhone à ce PC avec un câble et déverrouillez-le. Touchez Se fier si on vous le demande.",
        "Ouvrez l'app Appareils Apple (ou iTunes) et sélectionnez l'iPhone.",
        "Sous Sauvegardes, choisissez « Sauvegarder toutes les données de votre iPhone sur cet ordinateur ».",
        "Cochez « Chiffrer la sauvegarde locale » et choisissez un mot de passe dont vous vous souviendrez. Vous le saisirez ici dans un instant.",
        "Cliquez sur Sauvegarder maintenant et attendez la fin.",
      ],
      other: [
        "Installez libimobiledevice et connectez l'iPhone avec un câble. Déverrouillez-le et touchez Se fier.",
        "Activez le chiffrement une fois : idevicebackup2 encryption on",
        "Faites la sauvegarde : idevicebackup2 backup --full <dossier>",
        "Lancez l'assistant avec WHATFERRY_BACKUP_ROOT=<dossier> pour qu'il trouve la sauvegarde.",
      ],
    },
    now: {
      title: "Sauvegarder maintenant",
      lead: "whatferry fait lui-même la sauvegarde par le câble, comme le Finder. Connectez l'iPhone avec un câble et déverrouillez-le.",
      looking: "Recherche de l'iPhone…",
      connect: "Aucun iPhone trouvé. Connectez-le avec un câble, déverrouillez-le, puis cherchez à nouveau.",
      onlyOne: "Plusieurs iPhone sont connectés : ne laissez que celui à sauvegarder.",
      trust: "L'iPhone ne fait pas encore confiance à cet ordinateur. Sauvegarder maintenant le lui demande : touchez Se fier sur le téléphone, puis sauvegardez à nouveau.",
      found: (name) => `${name} trouvé.`,
      encrypts: "Ses sauvegardes sont chiffrées.",
      turnOnTitle: "Cet iPhone ne chiffre pas encore ses sauvegardes",
      turnOnBody: "Les discussions WhatsApp ne figurent que dans une sauvegarde chiffrée. Choisissez un mot de passe : désormais, l'iPhone chiffre chaque sauvegarde avec, et le Finder affiche « Chiffrer la sauvegarde locale » coché. L'iPhone peut demander son code.",
      choose: "Choisissez un mot de passe de sauvegarde",
      again: "Saisissez-le à nouveau",
      mismatch: "Les deux ne correspondent pas.",
      run: "Sauvegarder maintenant",
      lookAgain: "Chercher à nouveau",
      working: (p) => `Sauvegarde… ${Math.round(p)} %`,
      keepConnected: "Cela peut prendre une heure pour un iPhone plein. Gardez-le connecté et déverrouillé.",
      done: "Sauvegardé",
      turnedOn: "Le chiffrement est maintenant activé sur cet iPhone. Gardez le mot de passe : aucune de ses sauvegardes ne s'ouvre sans lui.",
      byHand: "Ou sauvegardez manuellement",
    },
    samePassphrase: "Utilisez le même mot de passe qu'avant. La nouvelle sauvegarde remplace l'ancienne dans le même dossier ; l'assistant a gardé ce dont il a besoin de la première.",
    chooseTitle: "Choisissez la sauvegarde",
    looking: "Recherche des sauvegardes…",
    noneTitle: "Aucune sauvegarde trouvée pour l'instant",
    lookedIn: (folders) => `Recherche effectuée dans ${folders}.`,
    noRoot: "Ce système n'a pas de dossier de sauvegarde standard : définissez WHATFERRY_BACKUP_ROOT.",
    encrypted: "Chiffrée",
    notEncrypted: "Non chiffrée",
    iphone: "iPhone",
    deviceLine: (model, ios, date) => `${model} · iOS ${ios} · sauvegardé le ${date}`,
    notEncryptedTitle: "Cette sauvegarde n'est pas chiffrée",
    notEncryptedBody: "Elle suffit pour vérifier, mais le transfert en demandera une chiffrée : cochez « Chiffrer la sauvegarde locale » et sauvegardez à nouveau.",
    passLabel: "Mot de passe de la sauvegarde",
    passHint: "Celui que vous avez choisi en cochant « Chiffrer la sauvegarde locale ». Utilisé une fois, jamais enregistré.",
    unlocking: "Déverrouillage de la sauvegarde. Cela prend une minute ou deux : la lenteur, c'est le chiffrement qui fait son travail.",
    reading: "Lecture de la sauvegarde…",
    check: { before: "Vérifier cette sauvegarde", after: "Vérifier et comparer" },
    checkAgain: "Vérifier à nouveau",
    resultLine: (model, ios, backed, checked) => `${model} · iOS ${ios} · sauvegardé le ${backed} · vérifié ${checked}`,
    noWhatsapp: "Cette sauvegarde ne contient aucune donnée WhatsApp. WhatsApp est-il installé sur cet iPhone ?",
    chatsIn: (path) => (
      <>
        Discussions dans <code className="font-mono text-xs">{path}</code>
      </>
    ),
    messagesRange: (a, b) => `Messages du ${a} au ${b}`,
    manyStores: (n) => `${n} bases de données de discussions : probablement une par compte.`,
    areasTitle: "Zones de stockage de WhatsApp",
    areasHead: ["Zone", "Fichiers", "Taille"],
    savedList: "Liste des fichiers de cette sauvegarde enregistrée, pour la comparer à la suivante.",
    diffTitle: "Ce que l'ajout du compte a changé",
    foundOne: "Base de données de discussions du nouveau compte trouvée",
    foundMany: (n) => `${n} nouvelles bases de données de discussions trouvées`,
    whereGo: "C'est là qu'iront les discussions Android.",
    noneNewTitle: "Aucune nouvelle base de données de discussions n'est apparue",
    noneNewBody: "Le deuxième compte partage peut-être celle qui existe, ou WhatsApp n'avait pas fini de le configurer avant la sauvegarde. La liste complète des changements est ci-dessous.",
    diffHead: ["Où", "Ajoutés", "Modifiés", "Supprimés"],
    filesAdded: "Fichiers ajoutés",
    filesChanged: "Fichiers modifiés",
  },
  destination: {
    title: "Où doivent aller les discussions Android ?",
    lead: "Choisissez quel compte WhatsApp de cet iPhone les reçoit. La suggestion vient de ce que montrent les sauvegardes.",
    suggested: "Suggéré",
    options: {
      setup: {
        title: "Configurer WhatsApp sur cet iPhone avec le numéro Android",
        body: "WhatsApp n'est pas encore configuré sur cet iPhone : le numéro Android devient son seul compte.",
      },
      second: {
        title: "Ajouter le numéro Android comme deuxième compte",
        body: "L'iPhone garde son compte actuel ; les discussions Android vont dans un nouveau compte vide à côté.",
      },
      existing: {
        title: "Un compte ici utilise déjà le numéro Android",
        body: "Les discussions Android vont dans ce compte. S'il a déjà des discussions, les deux historiques sont fusionnés.",
      },
    },
    reasons: {
      noWhatsapp: "Cette sauvegarde ne contient aucune donnée WhatsApp.",
      matches: (ends) =>
        `Un compte ici a un numéro se terminant par ${ends}, comme celui de la sauvegarde Android (seuls les deux derniers chiffres sont connus, vérifiez donc qu'il s'agit bien du même numéro).`,
      different: (ends, accounts) =>
        `Le numéro Android se termine par ${ends} ; les numéros des comptes de cet iPhone se terminent par ${accounts}.`,
      unknown: "La sauvegarde Android n'enregistre pas son numéro, l'assistant ne peut donc pas comparer.",
      stale: "Cette vérification de l'iPhone a été enregistrée avec une ancienne façon de lire les comptes de l'iPhone, qui pouvait prendre une discussion pour un compte. Cliquez sur Vérifier à nouveau ci-dessus pour comparer les numéros.",
      secondStarted: (ends) =>
        `Le numéro Android (se terminant par ${ends}) est déjà configuré ici comme deuxième compte, mais il n'a encore aucune discussion : la connexion s'est sans doute arrêtée avant le code de confirmation. Terminez la connexion sur l'iPhone, puis faites la deuxième sauvegarde.`,
      iphoneUnknown: (ends) =>
        `Le numéro Android se termine par ${ends}, mais les numéros des comptes de l'iPhone n'ont pas pu être lus dans cette sauvegarde.`,
    },
    full: "Cet iPhone a peut-être déjà un deuxième compte WhatsApp : la sauvegarde contient un dossier pour lui. Si c'est le cas, WhatsApp n'en autorisera peut-être pas un troisième, et vous devrez peut-être en supprimer un d'abord.",
    merge: (n) =>
      `Ce compte a déjà ${n} ${one(n) ? "message" : "messages"} sur cet iPhone. La fusion conserve les deux historiques, mais c'est le cas le plus difficile à réussir.`,
    notMatching: (ends, numbers) =>
      `Aucun compte ici n'a de numéro se terminant par ${ends}. Avec ce choix, les discussions Android vont dans un compte d'un autre numéro (se terminant par ${numbers}), et apparaîtront sous ce numéro.`,
    cantConfirm: "L'assistant ne peut pas confirmer qu'un compte ici utilise le numéro Android : vérifiez WhatsApp sur l'iPhone avant de choisir ceci.",
    replaceExisting: (numbers) =>
      `WhatsApp est déjà configuré sur cet iPhone${numbers ? ` (numéro se terminant par ${numbers})` : ""}. Le reconfigurer avec le numéro Android déconnecterait ce compte ; ajoutez plutôt un deuxième compte pour le garder.`,
    accountsTitle: "Comptes WhatsApp sur cet iPhone",
    account: (numberEnds, country, main, hasChats) =>
      `Numéro se terminant par ${numberEnds ?? "?"}${country ? ` (${country})` : ""} · ${main ? "compte principal" : "deuxième compte"}${hasChats ? "" : " · aucune discussion dans cette sauvegarde"}`,
    secondNoChats: "Les discussions de ce compte ne sont pas dans la sauvegarde de l'iPhone : soit il n'en a pas encore, soit WhatsApp exclut des sauvegardes les discussions d'un deuxième compte. Le transfert doit contourner cela, c'est donc la prochaine chose à découvrir.",
    folders: (n) =>
      `La sauvegarde contient aussi ${n} ${n <= 1 ? "dossier" : "dossiers"} que WhatsApp garde pour un autre compte, peut-être un deuxième ; son numéro est illisible.`,
    chooseFirst: "Vérifiez d'abord la sauvegarde de l'iPhone ; choisissez ensuite où vont les discussions.",
  },
  account: {
    setup: {
      title: "Configurez WhatsApp avec le numéro Android",
      lead: "WhatsApp crée sa base de données, ses dossiers et ses clés pour le numéro Android. La prochaine sauvegarde montre où ils se trouvent.",
      sectionTitle: "Configurez WhatsApp sur l'iPhone",
      steps: [
        "Installez WhatsApp depuis l'App Store, s'il n'est pas installé.",
        "Ouvrez-le et enregistrez le numéro du téléphone Android ; saisissez le code envoyé par WhatsApp. WhatsApp se déconnecte sur le téléphone Android : c'est normal, et votre fichier de sauvegarde est déjà en sécurité sur cet ordinateur.",
        "Si WhatsApp propose de restaurer des discussions, passez. Le compte doit démarrer vide.",
      ],
    },
    existing: {
      title: "Rien à ajouter sur l'iPhone",
      lead: "Le compte qui utilise déjà le numéro Android reçoit les discussions. Pas besoin de deuxième sauvegarde : passez aux résultats.",
    },
    none: "Choisissez d'abord où vont les discussions : c'est à la fin de l'étape de sauvegarde de l'iPhone.",
    goChoose: "Choisir où vont les discussions",
    notNeeded: "Inutile pour ce choix",
    skipNote: "Le compte qui reçoit les discussions existe déjà, il n'y a donc rien de nouveau à trouver. Passez aux résultats.",
    title: "Ajoutez le numéro Android sur l'iPhone",
    lead: "WhatsApp configure lui-même le deuxième compte : sa propre base de données vide, ses dossiers et ses clés. Ensuite, seul ce nouveau compte est rempli avec les discussions Android ; votre compte actuel n'est pas touché.",
    addTitle: "Ajoutez le compte sur l'iPhone",
    steps: [
      "Sur l'iPhone, ouvrez WhatsApp → Réglages et choisissez Ajouter un compte (à côté de votre nom, en haut).",
      "Enregistrez le numéro du téléphone Android et saisissez le code envoyé par WhatsApp. WhatsApp se déconnecte sur le téléphone Android : c'est normal, et votre fichier de sauvegarde est déjà en sécurité sur cet ordinateur.",
      "Si WhatsApp propose de restaurer des discussions pour le nouveau compte, passez. Le nouveau compte doit démarrer vide.",
    ],
    keepAndroid: "Gardez WhatsApp installé sur le téléphone Android jusqu'à la fin du transfert. En cas de problème, vous pourrez vous y reconnecter et vos discussions y seront toujours.",
  },
  convert: {
    title: "Convertissez les discussions",
    lead: "Fusionne l'historique du compte Android dans une copie de la base de données de discussions du compte iPhone. Rien ne change encore sur les téléphones ni dans la sauvegarde : parcourez le résultat ci-dessous avant d'écrire, et convertissez à nouveau avec un autre choix s'il ne convient pas.",
    needBackups: "Vérifiez d'abord la sauvegarde Android et une sauvegarde de l'iPhone.",
    goAndroid: "Aller à la sauvegarde Android",
    goIphone: "Aller à la sauvegarde de l'iPhone",
    targetTitle: "Quel compte de l'iPhone reçoit les discussions",
    leadToAndroid: "Fusionne l'historique du compte iPhone dans une copie de la base de données de discussions du compte Android. Rien ne change encore sur les téléphones ni dans les sauvegardes : parcourez le résultat ci-dessous avant d'écrire, et convertissez à nouveau avec un autre choix s'il ne convient pas.",
    sourceTitle: "Les discussions de quel compte de l'iPhone transférer",
    fromIphoneBackup: (date) => `Depuis la sauvegarde de l'iPhone vérifiée ${date}.`,
    mediaFromBackup: "Depuis la sauvegarde de l'iPhone",
    mediaFromBackupNote: "Les photos, vidéos, messages vocaux et documents présents sur l'iPhone, extraits de sa sauvegarde. Les plus anciens que WhatsApp a retirés de l'iPhone pour libérer de l'espace ne peuvent pas être récupérés.",
    androidNotWritableTitle: "La sauvegarde Android ne peut pas être réécrite",
    androidNotWritable: "Vérifiez à l'étape Android la sauvegarde chiffrée de bout en bout de WhatsApp (msgstore.db.crypt15, avec sa clé à 64 chiffres) : c'est celle que WhatsApp restaure.",
    notYetToAndroid: "Les réponses, réactions, sondages et appels ne sont pas encore transférés ; les messages eux-mêmes, si.",
    versionTitle: (kind) => `Pas la version ${kind} de WhatsApp sur laquelle whatferry a été vérifié`,
    fromBackup: (second, date) =>
      `Depuis la ${second ? "deuxième" : "première"} sauvegarde de l'iPhone, vérifiée ${date}.`,
    mainAccount: (ends) => `Compte principal${ends ? `, numéro se terminant par ${ends}` : ""}`,
    otherAccount: (ends) => `Compte ajouté${ends ? `, numéro se terminant par ${ends}` : ""}`,
    suggested: "Suggéré",
    hasMessages: (n) => `${n} ${one(n) ? "message" : "messages"} actuellement`,
    mergeNote: (n) =>
      `Ce compte a déjà ${n} ${one(n) ? "message" : "messages"}. Les discussions Android s'y ajoutent ; les discussions avec la même personne ou le même groupe sont réunies.`,
    mediaTitle: "Photos, vidéos et messages vocaux",
    mediaLead: "Le dossier Media de WhatsApp Android, copié sur cet ordinateur. Chaque dossier trouvé est comparé aux fichiers les plus récents cités dans les discussions Android.",
    mediaFound: (found, sampled) =>
      sampled ? `Contient ${found} des ${sampled} fichiers les plus récents cités dans les discussions` : "Les discussions ne citent aucun fichier média",
    mediaOther: "Un autre dossier",
    mediaPlaceholder: "Chemin vers une copie de WhatsApp/Media",
    mediaNone: "Sans médias",
    mediaNoneNote: "Les messages gardent leurs légendes ; les photos et vidéos elles-mêmes restent derrière.",
    working: "Conversion… une minute ou deux.",
    run: "Convertir",
    again: "Convertir à nouveau",
    doneTitle: (converted, total) => `${converted} messages sur ${total} convertis`,
    doneLine: (at) => `Converti ${at}.`,
    checksClean: "La base de données fusionnée a passé tous les contrôles de cohérence.",
    checksFailed: "La base de données fusionnée a échoué à un contrôle de cohérence",
    integrity: (result) => `intégrité : ${result}`,
    skipped: (n) =>
      one(n)
        ? `${n} événement que WhatsApp stocke différemment sur chaque téléphone (notifications système, appels, sondages, etc.) est laissé de côté.`
        : `${n} événements que WhatsApp stocke différemment sur chaque téléphone (notifications système, appels, sondages, etc.) sont laissés de côté.`,
    notYet: (what, n) => `${what} : ${n}, pas encore transférés (les messages eux-mêmes, si).`,
  },
  preview: {
    title: "Ce que le compte contiendra",
    loading: "Lecture du résultat…",
    // Each includes its preposition: the templates below put it straight after "messages".
    android: "d'Android",
    iphone: "de l'iPhone",
    totals: (fresh, joined, unchanged, messages, from) =>
      `${fresh} ${one(fresh) ? "nouvelle discussion" : "nouvelles discussions"} et ${joined} ${one(joined) ? "réunie" : "réunies"} à des discussions existantes (${messages} ${one(messages) ? "message" : "messages"} ${from}) ; ${unchanged} ${one(unchanged) ? "discussion inchangée" : "discussions inchangées"}.`,
    fromSource: (from) => from.charAt(0).toUpperCase() + from.slice(1),
    all: "Toutes les discussions",
    search: "Rechercher par nom ou numéro",
    noChats: "Aucune discussion ne correspond.",
    group: "Groupe",
    change: { new: "Nouvelle", joined: "Réunie", unchanged: "Inchangée" },
    chatLine: (moved, total, first, last, from) => `${moved} messages sur ${total} ${from} · du ${first} au ${last}`,
    showAll: (n) => `Tout afficher (${n})`,
    newest: (n, from) => `messages les plus récents sur ${n} ; ceux encadrés viennent ${from}`,
    kinds: {
      image: "Photo",
      video: "Vidéo",
      audio: "Message vocal ou audio",
      contact: "Fiche contact",
      location: "Position",
      document: "Document",
      gif: "GIF",
      sticker: "Autocollant",
      deleted: "Ce message a été supprimé",
      link: "Lien",
      system: "Événement de discussion",
      other: "Autre message",
    },
  },
  write: {
    title: "Écrivez une nouvelle sauvegarde",
    lead: "Copie la sauvegarde de l'iPhone et place les discussions converties dans la copie, chiffrées comme le fait iOS. Chaque fichier écrit est relu et vérifié.",
    needConvert: "Convertissez d'abord les discussions.",
    goConvert: "Aller à Convertir",
    fromTitle: "La sauvegarde de départ",
    from: (date) => `La sauvegarde de l'iPhone du ${date}, dans laquelle les discussions ont été converties :`,
    untouched: "Cette sauvegarde reste telle quelle ; la nouvelle va dans le dossier propre à whatferry.",
    previewFirst: "Ce qui est écrit est la conversion telle que son aperçu la montre.",
    openPreview: "Parcourir l'aperçu",
    passTitle: "Mot de passe",
    leadToAndroid: "Chiffre la base de données convertie comme une sauvegarde WhatsApp à part entière, avec la clé à 64 chiffres de la sauvegarde Android, et la range avec les photos et vidéos comme WhatsApp les range. Elle est ensuite déchiffrée à nouveau et vérifiée.",
    fromAndroid: "La sauvegarde Android dans laquelle les discussions ont été converties :",
    keyTitle: "La clé de la sauvegarde Android",
    keyLabel: "Clé à 64 chiffres",
    keyHint: "La clé que WhatsApp a affichée quand vous avez activé la sauvegarde chiffrée de bout en bout. Utilisée une fois, jamais enregistrée.",
    skipNoteToAndroid: "Normalement refusé : la sauvegarde Android doit être celle dans laquelle les discussions ont été converties. Avec cette option, ce que WhatsApp a reçu sur le téléphone Android après cette sauvegarde est perdu à la restauration.",
    changedBodyToAndroid: "Vérifiez à nouveau la sauvegarde Android la plus récente à son étape, puis convertissez à nouveau. Cela garde tout ce que le compte contient maintenant.",
    addedToAndroid: (bytes, media) =>
      `msgstore.db.crypt15 (${bytes}), déchiffré à nouveau et vérifié, et ${media} fichiers médias, prêts à copier sur le téléphone.`,
    noPass: "Cette sauvegarde n'est pas chiffrée : aucun mot de passe nécessaire.",
    skipLabel: "Écrire même si la sauvegarde a changé depuis la conversion",
    skipNote: "Normalement refusé : la sauvegarde doit être celle dans laquelle les discussions ont été converties. Avec cette option, ce que le compte a reçu sur l'iPhone après la conversion est perdu à la restauration.",
    changedTitle: "Cette sauvegarde a changé après la conversion",
    changedBody: "Vérifiez à nouveau la sauvegarde de l'iPhone la plus récente à son étape, puis convertissez à nouveau. Cela garde tout ce que le compte contient maintenant.",
    working: "Écriture… quelques minutes pour une grosse sauvegarde.",
    run: "Écrire la nouvelle sauvegarde",
    again: "Écrire à nouveau",
    doneTitle: "Nouvelle sauvegarde écrite et vérifiée",
    unchecked: "source non vérifiée",
    doneLine: (at) => `Écrite ${at}.`,
    added: (files, bytes, verified) =>
      `${files} ${one(files) ? "fichier ajouté" : "fichiers ajoutés"} (${bytes}) ; ${verified} ${one(verified) ? "fichier relu et vérifié" : "fichiers relus et vérifiés"}.`,
  },
  copy: {
    title: "Copiez sur le téléphone Android",
    lead: "Place la nouvelle sauvegarde et ses médias dans le dossier de WhatsApp sur le téléphone, en USB. WhatsApp la restaure ensuite, comme n'importe laquelle de ses propres sauvegardes.",
    warnTitle: "WhatsApp sur le téléphone Android repart de cette sauvegarde",
    warnBody: "La restauration remplace les discussions WhatsApp du téléphone Android par celles de la sauvegarde : les discussions du compte telles qu'elles étaient lors de sa sauvegarde, plus celles de l'iPhone. Rien d'autre ne change sur le téléphone.",
    beforeTitle: "Avant de commencer",
    before: [
      "Si quelque chose est arrivé dans WhatsApp sur le téléphone Android depuis la sauvegarde que vous avez vérifiée, sauvegardez à nouveau et refaites l'étape Android, Convertir et Écrire.",
      "Effacez les données de WhatsApp : Paramètres → Applications → WhatsApp → Stockage → Vider le stockage. WhatsApp se déconnecte sur ce téléphone ; les discussions reviennent depuis la sauvegarde.",
      "Connectez le téléphone avec un câble, débogage USB activé (comme à l'étape Android), et déverrouillez-le.",
    ],
    phoneTitle: "Le téléphone Android",
    looking: "Recherche du téléphone…",
    noAdbTitle: "adb n'est pas installé",
    noAdb: "Installez-le comme l'explique l'étape Android, ou copiez le dossier manuellement (ci-dessous).",
    noPhoneTitle: "Aucun téléphone trouvé",
    noPhone: "Connectez le téléphone avec un câble, activez le débogage USB, déverrouillez-le et cherchez à nouveau.",
    ready: "Prêt",
    whichFolder: "Quel dossier WhatsApp sur le téléphone (un par compte) :",
    lookAgain: "Chercher à nouveau",
    confirmTitle: "Confirmer",
    cleared: "J'ai vidé le stockage de WhatsApp sur le téléphone (étape 1.2).",
    working: "Copie… quelques minutes s'il y a beaucoup de photos.",
    run: "Copier sur le téléphone",
    again: "Copier à nouveau",
    doneTitle: "Copié sur le téléphone",
    doneLine: (at, media) => `Copié ${at}, avec ${media} ${one(media) ? "fichier média" : "fichiers médias"}. Ensuite :`,
    kept: (path) => `La sauvegarde d'origine du téléphone est conservée sous ${path}.`,
    after: [
      "Ouvrez WhatsApp, acceptez les conditions et vérifiez le même numéro.",
      "Quand WhatsApp trouve la sauvegarde, appuyez sur Restaurer et saisissez la clé à 64 chiffres.",
      "Attendez la fin, puis parcourez les discussions.",
    ],
    manualTitle: "Sans débogage USB",
    manual: "Copiez le contenu de ce dossier :",
    manualInto: "dans ce dossier du téléphone par transfert de fichiers USB, après avoir renommé le Databases/msgstore.db.crypt15 du téléphone pour le garder :",
  },
  restore: {
    title: "Restaurez sur l'iPhone",
    lead: "Place la nouvelle sauvegarde sur l'iPhone par le câble, comme le fait Restaurer la sauvegarde dans le Finder.",
    needWrite: "Écrivez d'abord la nouvelle sauvegarde.",
    goWrite: "Aller à Écrire",
    warnTitle: "Cela remplace tout le contenu de l'iPhone",
    warnBody: (date) =>
      `L'iPhone revient à son état lors de sa sauvegarde du ${date}, plus les discussions converties. Tout ce qu'il a reçu après (messages, photos, données d'apps) disparaît.`,
    beforeTitle: "Avant de commencer",
    before: [
      "Dans WhatsApp sur l'iPhone, sauvegardez les discussions de chaque compte sur iCloud (Réglages → Discussions → Sauvegarde → Sauvegarder maintenant). C'est le chemin du retour en cas de problème.",
      "Gardez l'iPhone en mode Avion de la sauvegarde jusqu'à la fin de la restauration, ou faites une nouvelle sauvegarde et refaites Convertir.",
      "Désactivez Localiser. Si la Protection en cas de vol de l'appareil est activée, iOS demande de la désactiver d'abord : Réglages → Face ID et code → Protection en cas de vol de l'appareil → désactiver (hors d'un lieu familier, iOS vous fait attendre une heure). Puis Réglages → votre nom → Localiser → Localiser mon iPhone → désactiver.",
      "Connectez l'iPhone avec un câble, déverrouillez-le et gardez-le déverrouillé. Fermez sa fenêtre dans le Finder.",
    ],
    phoneTitle: "L'iPhone",
    looking: "Recherche de l'iPhone…",
    noPhone: "L'iPhone de cette sauvegarde n'est pas connecté",
    noPhoneBody: (others) =>
      others
        ? `${others > 1 ? `${others} autres iPhone sont connectés` : "Un autre iPhone est connecté"}, mais pas celui de cette sauvegarde. Connectez le bon et cherchez à nouveau.`
        : "Connectez-le avec un câble, déverrouillez-le et cherchez à nouveau.",
    phoneLine: (ios) => `iOS ${ios}, connecté par câble`,
    matches: "La nouvelle sauvegarde vient de cet iPhone",
    trusted: "Cet ordinateur est approuvé",
    notTrusted: "Pas encore approuvé : déverrouillez l'iPhone, touchez Se fier et cherchez à nouveau",
    findMyOff: "Localiser est désactivé",
    findMyOn: "Localiser est activé : désactivez-le (d'abord la Protection en cas de vol de l'appareil, si elle est activée), puis cherchez à nouveau",
    findMyUnknown: "Localiser : impossible à savoir. Déverrouillez l'iPhone et cherchez à nouveau",
    lookAgain: "Chercher à nouveau",
    confirmTitle: "Confirmer",
    typeName: (name) => `Saisissez ${name} pour confirmer`,
    working: (percent) => `Restauration… ${Math.round(percent)} %`,
    keepConnected: "Gardez l'iPhone connecté et déverrouillé jusqu'à ce qu'il redémarre.",
    run: "Restaurer l'iPhone",
    doneTitle: "Restauré",
    doneLine: (at) => `Restauré ${at}. Ensuite :`,
    after: [
      "L'iPhone redémarre et termine la restauration. Gardez-le connecté jusqu'à l'écran verrouillé, puis déverrouillez-le.",
      "Les apps se réinstallent depuis l'App Store en arrière-plan : attendez WhatsApp.",
      "Ouvrez WhatsApp, passez au compte qui a reçu les discussions et parcourez-les. S'il demande de vérifier le numéro, faites-le. S'il propose de restaurer l'historique des discussions depuis iCloud, passez : cela remplacerait les discussions converties.",
      "Réactivez Localiser, puis la Protection en cas de vol de l'appareil.",
    ],
  },
  results: {
    title: "Résultats",
    lead: "Ce résumé contient des nombres, des versions et des emplacements de fichiers : aucun message, nom ni numéro de téléphone. Transmettez-le si quelque chose doit être examiné.",
    summaryLabel: "Résumé",
    summaryLanguage: "Le résumé est en anglais pour pouvoir être envoyé au développeur.",
    copy: "Copier le résumé",
    copied: "Copié",
    nextTitle: "La suite",
    next: "Une fois l'iPhone redémarré, ouvrez WhatsApp et vérifiez le compte qui a reçu les discussions. Pour transférer un autre compte Android, vérifiez sa sauvegarde à l'étape Android et refaites les étapes.",
    cleanTitle: "Nettoyage",
    clean: (home) => (
      <>
        Les copies déchiffrées sont dans <Code>{home}</Code>. Supprimez ce dossier quand vous voulez ; le résumé ci-dessus
        n'en a pas besoin.
      </>
    ),
    startOver: "Recommencer",
    confirmReset: "Oublier toute la progression ? Les copies déchiffrées restent sur le disque jusqu'à ce que vous les supprimiez.",
  },
}
