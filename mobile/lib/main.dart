
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:uuid/uuid.dart';
import 'theme.dart';


import 'chat_engine.dart';
import 'offline_cache.dart';
import 'expert_chat_page.dart';
import 'knowledge_chat_page.dart';
import 'scan_flow.dart';
const moreCropKeys = ['maize', 'cassava', 'tomato', 'beans', 'groundnuts', 'rice', 'sorghum', 'millet', 'sweet_potato', 'banana', 'onion', 'cabbage'];
const moreAnimalKeys = ['chicken', 'goats', 'cattle', 'pigs', 'sheep', 'ducks'];





const kApiBase = String.fromEnvironment('API_BASE', defaultValue: 'http://10.0.2.2:8000');

const hostNames = {
  'maize': {'en': 'Maize', 'ny': 'Chimanga', 'fr': 'Maïs', 'sw': 'Mahindi', 'pt': 'Milho'},
  'cassava': {'en': 'Cassava', 'ny': 'Chinangwa', 'fr': 'Manioc', 'sw': 'Muhogo', 'pt': 'Mandioca'},
  'tomato': {'en': 'Tomato', 'ny': 'Tomato', 'fr': 'Tomate', 'sw': 'Nyanya', 'pt': 'Tomate'},
  'beans': {'en': 'Beans', 'ny': 'Nyemba', 'fr': 'Haricots', 'sw': 'Maharagwe', 'pt': 'Feijão'},
  'groundnuts': {'en': 'Groundnuts', 'ny': 'Mtedza', 'fr': 'Arachides', 'sw': 'Karanga', 'pt': 'Amendoim'},
  'rice': {'en': 'Rice', 'ny': 'Mpunga', 'fr': 'Riz', 'sw': 'Mchele', 'pt': 'Arroz'},
  'chicken': {'en': 'Chickens', 'ny': 'Nkhuku', 'fr': 'Poules', 'sw': 'Kuku', 'pt': 'Galinhas'},
  'goats': {'en': 'Goats', 'ny': 'Mbuzi', 'fr': 'Chèvres', 'sw': 'Mbuzi', 'pt': 'Cabras'},
  'cattle': {'en': 'Cattle', 'ny': "Ng'ombe", 'fr': 'Bovins', 'sw': "Ng'ombe", 'pt': 'Gado'},
};


const ui = {
  'en': {
    'farm': 'My Farm', 'check': 'Check', 'experts': 'Experts', 'analytics': 'Farm overview',
    'alerts': 'Alerts', 'recent': 'Recent', 'yourFarm': 'Crops & animals',
    'emptyFarm': 'Add what you grow or raise', 'add': 'Add', 'period': 'Season / period', 'save': 'Save',
    'lang': 'Language', 'online': 'Online', 'offline': 'Offline', 'sync': 'Sync',
    'crop': 'Crops', 'animal': 'Animals', 'hold': 'Hold steady', 'point': 'Point at the problem',
    'result': 'Result', 'likely': 'Likely issue', 'cando': 'What to do', 'callExpert': 'Call expert',
    'danger': 'Danger signs?', 'banner': 'Pilot: published guidance only.',
    'noCases': 'No scans yet', 'thisWeek': 'This week', 'hosts': 'On the farm',
    'checks': 'Checks', 'openAlerts': 'Alerts', 'published': 'Guides',
    'farmHealth': 'Farm Health', 'healthy': 'Healthy', 'allGood': 'All good', 'checkAlerts': 'Check alerts',
    'needsCare': 'Needs care', 'ok': 'OK', 'quickStats': 'Quick Stats', 'crops': 'Crops', 'animals': 'Animals',
    'guides': 'Guides', 'scans': 'Scans', 'myCropsAnimals': 'My crops & animals',
    'refreshPacks': 'Refresh packs', 'farmName': 'Farm name', 'cancel': 'Cancel',
    'greetingMorning': 'Good morning', 'greetingAfternoon': 'Good afternoon', 'greetingEvening': 'Good evening',
    'offlinePack': 'Offline pack', 'guidesOfficers': 'Guides {p} · Officers {e}', 'libraryN': 'Library {n}',
    'alertN': '{n} alert(s)', 'continueChat': 'Continue — chat then advice',
    'confirmDescribe': 'Confirm plant/animal & describe', 'getAdvice': 'Get advice',
    'scanChat': 'Scan chat', 'message': 'Message…', 'send': 'Send', 'voiceNote': 'Voice note', 'play': 'Play',
    'recording': 'Recording… tap mic again to send', 'noMessages': 'No messages yet. Say hello or describe the problem.',
    'videoRequest': 'Video request', 'videoCall': 'Video call', 'voiceCall': 'Voice call',
    'fieldPackReady': 'Field pack ready on this phone', 'downloadPacks': 'Download packs before field work',
    'downloadRefresh': 'Download / refresh packs',
    'chatFirstBanner': 'Chat first — advice only when you ask (or tap Get advice). Works offline with saved packs.',
    'askHost': 'Before any advice: what plant or animal is this? Type the name (e.g. maize, goat, chicken).',
    'identifyConfirm': 'From your scan and our library this looks like {h} ({o}). Is that correct? Type yes or the correct name.',
    'prevScans': 'Previous scans of {h} on this phone:',
    'photoSuggest': 'Photo received. Suggested: {h} ({o}). Type yes or the correct name.',
    'historyEpisode': '{d}: {c} — {n}',
    'identifyAsk': 'I could not match this photo to a published host yet. What plant or animal is this? Type the name.',
    'clarifyMore': 'Thank you. Describe signs (spots, wilting, weak animals…). This helps match published guidance.',
    'askDesc': 'Thank you. What do you see? (spots, wilting, animals weak…). Describe in your own words.',
    'howAdvice': 'When you want guidance, type "advice" or "help me" or "give advice". I only use expert-published steps.',
    'typeAnswer': 'Type your answer…', 'assistant': 'Assistant', 'you': 'You',
    'savedKb': 'Saved for shared knowledge (expert still approves treatments).',
    'offlineAdvice': 'Offline pack guidance',
    'noPack': 'No published guidance on this phone for that crop/animal yet. Connect once to download packs, or ask an officer.',
    'analyse': 'Analyse scan', 'extraNotes': 'Extra notes (optional)',
    'dangerSigns': 'Danger signs (many deaths, bloody discharge, cannot stand)',
    'takePhoto': 'Take photo', 'chooseGallery': 'Gallery', 'symptoms': 'Symptoms',
    'availableOfficers': 'Available officers', 'noOfficers': 'No officers listed yet. Register on the portal.',
    'chat': 'Chat', 'call': 'Call', 'district': 'District', 'other': 'Other',
    'prevention': 'Prevention / signs', 'medications': 'Medications (published)', 'outcome': 'Outcome',
    'rememberHost': 'We remember this is {h}. You can update what you see, or tap Get advice / type advice.',
    'lastNotes': 'Last notes: {n}',
    'noPackTip': 'Tip: An officer must Publish a procedure for host {h}. Then open My Farm and Refresh packs while online.',
    'packLine': 'Guides: {p} · Officers: {e} · Library: {l}',
  },
  'ny': {
    'farm': 'Munda', 'check': 'Onani', 'experts': 'Akatswiri', 'analytics': 'Munda wanga',
    'alerts': 'Chenjezo', 'recent': 'Posachedwa', 'yourFarm': 'Mbewu ndi ziweto',
    'emptyFarm': 'Onjezani zomwe mumalima', 'add': 'Onjezani', 'period': 'Nyengo', 'save': 'Sungeni',
    'lang': 'Chilankhulo', 'online': 'Pa intaneti', 'offline': 'Sipali intaneti', 'sync': 'Sync',
    'crop': 'Mbewu', 'animal': 'Ziweto', 'hold': 'Gwiritsani', 'point': 'Lolani vuto',
    'result': 'Zotsatira', 'likely': 'Vuto', 'cando': 'Chochita', 'callExpert': 'Imbani',
    'danger': 'Zoopsa?', 'banner': 'Yeso: uphungu wovomerezedwa.',
    'noCases': 'Palibe', 'thisWeek': 'Sabata ino', 'hosts': 'Pa munda',
    'checks': 'Kuwona', 'openAlerts': 'Chenjezo', 'published': 'Uphungu',
    'farmHealth': 'Thanzi la munda', 'healthy': 'Bwino', 'allGood': 'Zabwino zonse', 'checkAlerts': "Yang'anirani",
    'needsCare': 'Osamalitsa', 'ok': 'Chabwino', 'quickStats': 'Ziwerengero', 'crops': 'Mbewu', 'animals': 'Ziweto',
    'guides': 'Uphungu', 'scans': 'Kuwona', 'myCropsAnimals': 'Mbewu ndi ziweto zanga',
    'refreshPacks': 'Tsitsani uphungu', 'farmName': 'Dzina la munda', 'cancel': 'Siya',
    'greetingMorning': 'Mwadzuka bwanji', 'greetingAfternoon': 'Mwaswera bwanji', 'greetingEvening': 'Madzulo abwino',
    'offlinePack': 'Pa foni', 'guidesOfficers': 'Uphungu {p} · Akatswiri {e}', 'libraryN': 'Library {n}',
    'alertN': 'Chenjezo {n}', 'continueChat': 'Pitirizani — zokambirana kenako uphungu',
    'confirmDescribe': 'Tsimikizani mbewu/chiweto ndi kufotokoza', 'getAdvice': 'Pezani uphungu',
    'scanChat': 'Zokambirana', 'message': 'Uthenga…', 'send': 'Tumizani', 'voiceNote': 'Mawu', 'play': 'Tsegulani',
    'recording': 'Kujambula… dinani mic kuti mutumize', 'noMessages': 'Palibe uthenga. Yankhulani.',
    'videoRequest': 'Kanema', 'videoCall': 'Kuyimba kanema', 'voiceCall': 'Kuyimba',
    'fieldPackReady': 'Uphungu uli pa foni', 'downloadPacks': 'Tsitsani uphungu musanapite kumunda',
    'downloadRefresh': 'Tsitsani / sinthani uphungu',
    'chatFirstBanner': 'Yankhulani poyamba — uphungu mukapempha. Zimagwira ngakhale sipali intaneti.',
    'askHost': 'Musanalandire uphungu: ndi mbewu kapena chiweto chanji? Lemani dzina.',
    'askDesc': 'Zikomo. Mukuwona chiyani? Fotokozerani.',
    'howAdvice': 'Mukafuna uphungu, lembani "uphungu" kapena "thandizeni".',
    'typeAnswer': 'Lembani yankho…', 'assistant': 'Mthandizi', 'you': 'Inu',
    'savedKb': 'Zasungidwa. Katswiri amavomereza chithandizo.',
    'offlineAdvice': 'Uphungu wa pa foni',
    'noPack': 'Palibe uphungu pa foni. Lumikizani kuti mutseke packs, kapena funsani officer.',
    'analyse': 'Onani', 'extraNotes': 'Zina (mwakufuna)',
    'dangerSigns': 'Zoopsa (imfa zambiri, magazi, sangathe kuyimirira)',
    'takePhoto': 'Jambula', 'chooseGallery': 'Gallery', 'symptoms': 'Zizindikiro',
    'availableOfficers': 'Akatswiri omwe alipo', 'noOfficers': 'Palibe akatswiri. Lembani pa portal.',
    'chat': 'Zokambirana', 'call': 'Imbani', 'district': 'Boma', 'other': 'Zina',
    'prevention': 'Kupewa / zizindikiro', 'outcome': 'Zotsatira',
    'rememberHost': 'Tikukumbukira kuti ndi {h}. Mutha kusintha zomwe mukuwona, kapena dinani Pezani uphungu / lembani uphungu.',
    'lastNotes': 'Zolembedwa: {n}',
    'noPackTip': 'Uphungu: Katswiri ayenera kusindikiza njira ya {h}. Kenako pa Munda → Tsitsani uphungu pa intaneti.',
    'packLine': 'Uphungu: {p} · Akatswiri: {e} · Library: {l}',
  },
  'fr': {
    'farm': 'Ferme', 'check': 'Vérifier', 'experts': 'Experts', 'analytics': 'Aperçu',
    'alerts': 'Alertes', 'recent': 'Récent', 'yourFarm': 'Cultures et animaux',
    'emptyFarm': 'Ajoutez ce que vous cultivez', 'add': 'Ajouter', 'period': 'Saison', 'save': 'Enregistrer',
    'lang': 'Langue', 'online': 'En ligne', 'offline': 'Hors ligne', 'sync': 'Sync',
    'crop': 'Cultures', 'animal': 'Animaux', 'hold': 'Tenez ferme', 'point': 'Visez le problème',
    'result': 'Résultat', 'likely': 'Problème', 'cando': 'Que faire', 'callExpert': 'Appeler',
    'danger': 'Danger ?', 'banner': 'Pilote : conseils publiés seulement.',
    'noCases': 'Aucun', 'thisWeek': 'Cette semaine', 'hosts': 'À la ferme',
    'checks': 'Contrôles', 'openAlerts': 'Alertes', 'published': 'Guides',
    'farmHealth': 'Santé de la ferme', 'healthy': 'Saine', 'allGood': 'Tout va bien', 'checkAlerts': 'Voir alertes',
    'needsCare': 'À surveiller', 'ok': 'OK', 'quickStats': 'Statistiques', 'crops': 'Cultures', 'animals': 'Animaux',
    'guides': 'Guides', 'scans': 'Scans', 'myCropsAnimals': 'Mes cultures et animaux',
    'refreshPacks': 'Actualiser', 'farmName': 'Nom de la ferme', 'cancel': 'Annuler',
    'greetingMorning': 'Bonjour', 'greetingAfternoon': 'Bon après-midi', 'greetingEvening': 'Bonsoir',
    'offlinePack': 'Pack hors ligne', 'guidesOfficers': 'Guides {p} · Experts {e}', 'libraryN': 'Bibliothèque {n}',
    'alertN': '{n} alerte(s)', 'continueChat': 'Continuer — discussion puis conseils',
    'confirmDescribe': 'Confirmer plante/animal et décrire', 'getAdvice': 'Obtenir des conseils',
    'scanChat': 'Discussion', 'message': 'Message…', 'send': 'Envoyer', 'voiceNote': 'Note vocale', 'play': 'Lire',
    'recording': 'Enregistrement… appuyez encore pour envoyer', 'noMessages': 'Pas de messages. Dites bonjour.',
    'videoRequest': 'Demande vidéo', 'videoCall': 'Appel vidéo', 'voiceCall': 'Appel',
    'fieldPackReady': 'Pack prêt sur ce téléphone', 'downloadPacks': 'Téléchargez les packs avant le terrain',
    'downloadRefresh': 'Télécharger / actualiser',
    'chatFirstBanner': 'Discussion d’abord — conseils quand vous demandez. Fonctionne hors ligne.',
    'askHost': 'Avant tout conseil : quelle plante ou animal ? Écrivez le nom.',
    'askDesc': 'Merci. Que voyez-vous ? Décrivez.',
    'howAdvice': 'Pour les conseils, écrivez « conseil » ou « aide ».',
    'typeAnswer': 'Votre réponse…', 'assistant': 'Assistant', 'you': 'Vous',
    'savedKb': 'Enregistré (un expert valide les traitements).',
    'offlineAdvice': 'Conseils hors ligne',
    'noPack': 'Pas de guide sur ce téléphone. Connectez-vous une fois ou demandez un expert.',
    'analyse': 'Analyser', 'extraNotes': 'Notes (optionnel)',
    'dangerSigns': 'Signes de danger (morts nombreuses, sang, ne peut pas se tenir)',
    'takePhoto': 'Photo', 'chooseGallery': 'Galerie', 'symptoms': 'Symptômes',
    'availableOfficers': 'Experts disponibles', 'noOfficers': 'Aucun expert. Inscrivez-les sur le portail.',
    'chat': 'Discussion', 'call': 'Appeler', 'district': 'District', 'other': 'Autre',
    'prevention': 'Prévention / signes', 'outcome': 'Résultat',
    'rememberHost': 'Nous nous souvenons que c’est {h}. Mettez à jour ce que vous voyez, ou demandez des conseils.',
    'lastNotes': 'Dernières notes : {n}',
    'noPackTip': 'Un expert doit Publier une procédure pour {h}. Puis Ferme → Actualiser les packs en ligne.',
    'packLine': 'Guides : {p} · Experts : {e} · Bibliothèque : {l}',
  },
  'sw': {
    'farm': 'Shamba', 'check': 'Angalia', 'experts': 'Wataalamu', 'analytics': 'Muhtasari',
    'alerts': 'Tahadhari', 'recent': 'Hivi karibuni', 'yourFarm': 'Mazao na mifugo',
    'emptyFarm': 'Ongeza unacholima', 'add': 'Ongeza', 'period': 'Msimu', 'save': 'Hifadhi',
    'lang': 'Lugha', 'online': 'Mtandaoni', 'offline': 'Nje ya mtandao', 'sync': 'Sync',
    'crop': 'Mazao', 'animal': 'Mifugo', 'hold': 'Shikilia', 'point': 'Elekeza tatizo',
    'result': 'Matokeo', 'likely': 'Tatizo', 'cando': 'Fanya', 'callExpert': 'Piga',
    'danger': 'Hatari?', 'banner': 'Majaribio: taratibu zilizochapishwa tu.',
    'noCases': 'Hakuna', 'thisWeek': 'Wiki hii', 'hosts': 'Shambani',
    'checks': 'Ukaguzi', 'openAlerts': 'Tahadhari', 'published': 'Mwongozo',
    'farmHealth': 'Afya ya shamba', 'healthy': 'Sawa', 'allGood': 'Vyote vizuri', 'checkAlerts': 'Angalia tahadhari',
    'needsCare': 'Inahitaji uangalifu', 'ok': 'Sawa', 'quickStats': 'Takwimu', 'crops': 'Mazao', 'animals': 'Wanyama',
    'guides': 'Mwongozo', 'scans': 'Ukaguzi', 'myCropsAnimals': 'Mazao na mifugo yangu',
    'refreshPacks': 'Onyesha upya', 'farmName': 'Jina la shamba', 'cancel': 'Ghairi',
    'greetingMorning': 'Habari za asubuhi', 'greetingAfternoon': 'Habari za mchana', 'greetingEvening': 'Habari za jioni',
    'offlinePack': 'Pakiti nje ya mtandao', 'guidesOfficers': 'Mwongozo {p} · Wataalamu {e}', 'libraryN': 'Maktaba {n}',
    'alertN': 'Tahadhari {n}', 'continueChat': 'Endelea — mazungumzo kisha ushauri',
    'confirmDescribe': 'Thibitisha mmea/mnyama na eleza', 'getAdvice': 'Pata ushauri',
    'scanChat': 'Mazungumzo', 'message': 'Ujumbe…', 'send': 'Tuma', 'voiceNote': 'Sauti', 'play': 'Cheza',
    'recording': 'Inarekodi… gusa mic tena kutuma', 'noMessages': 'Hakuna ujumbe. Salimu.',
    'videoRequest': 'Ombi la video', 'videoCall': 'Simu ya video', 'voiceCall': 'Piga simu',
    'fieldPackReady': 'Pakiti iko kwenye simu', 'downloadPacks': 'Pakua pakiti kabla ya shamba',
    'downloadRefresh': 'Pakua / onyesha upya',
    'chatFirstBanner': 'Mazungumzo kwanza — ushauri unapouliza. Inafanya kazi nje ya mtandao.',
    'askHost': 'Kabla ya ushauri: ni mmea au mnyama gani? Andika jina.',
    'askDesc': 'Asante. Unaona nini? Eleza.',
    'howAdvice': 'Unapotaka ushauri, andika "ushauri" au "nisaidie".',
    'typeAnswer': 'Andika jibu…', 'assistant': 'Msaidizi', 'you': 'Wewe',
    'savedKb': 'Imehifadhiwa (mtaalamu aidhinishe matibabu).',
    'offlineAdvice': 'Ushauri nje ya mtandao',
    'noPack': 'Hakuna mwongozo kwenye simu. Unganisha mara moja au muulize afisa.',
    'analyse': 'Chambua', 'extraNotes': 'Maelezo (hiari)',
    'dangerSigns': 'Ishara za hatari (vifo vingi, damu, hawezi kusimama)',
    'takePhoto': 'Piga picha', 'chooseGallery': 'Ghalani', 'symptoms': 'Dalili',
    'availableOfficers': 'Wataalamu waliopo', 'noOfficers': 'Hakuna. Sajili kwenye portal.',
    'chat': 'Mazungumzo', 'call': 'Piga', 'district': 'Wilaya', 'other': 'Nyingine',
    'prevention': 'Kinga / ishara', 'outcome': 'Matokeo',
    'rememberHost': 'Tunakumbuka hii ni {h}. Unaweza kusasisha unachoona, au gusa Pata ushauri.',
    'lastNotes': 'Maelezo ya awali: {n}',
    'noPackTip': 'Afisa lazima Achapishe taratibu ya {h}. Kisha Shamba → Pakua pakiti mtandaoni.',
    'packLine': 'Mwongozo: {p} · Wataalamu: {e} · Maktaba: {l}',
  },
  'pt': {
    'farm': 'Quinta', 'check': 'Verificar', 'experts': 'Especialistas', 'analytics': 'Resumo',
    'alerts': 'Alertas', 'recent': 'Recente', 'yourFarm': 'Culturas e animais',
    'emptyFarm': 'Adicione o que cultiva', 'add': 'Adicionar', 'period': 'Época', 'save': 'Guardar',
    'lang': 'Idioma', 'online': 'Online', 'offline': 'Offline', 'sync': 'Sync',
    'crop': 'Culturas', 'animal': 'Animais', 'hold': 'Mantenha firme', 'point': 'Aponte o problema',
    'result': 'Resultado', 'likely': 'Problema', 'cando': 'O que fazer', 'callExpert': 'Ligar',
    'danger': 'Perigo?', 'banner': 'Piloto: só procedimentos publicados.',
    'noCases': 'Nenhum', 'thisWeek': 'Esta semana', 'hosts': 'Na quinta',
    'checks': 'Verificações', 'openAlerts': 'Alertas', 'published': 'Guias',
    'farmHealth': 'Saúde da quinta', 'healthy': 'Saudável', 'allGood': 'Tudo bem', 'checkAlerts': 'Ver alertas',
    'needsCare': 'Precisa de cuidado', 'ok': 'OK', 'quickStats': 'Estatísticas', 'crops': 'Culturas', 'animals': 'Animais',
    'guides': 'Guias', 'scans': 'Verificações', 'myCropsAnimals': 'As minhas culturas e animais',
    'refreshPacks': 'Atualizar', 'farmName': 'Nome da quinta', 'cancel': 'Cancelar',
    'greetingMorning': 'Bom dia', 'greetingAfternoon': 'Boa tarde', 'greetingEvening': 'Boa noite',
    'offlinePack': 'Pacote offline', 'guidesOfficers': 'Guias {p} · Especialistas {e}', 'libraryN': 'Biblioteca {n}',
    'alertN': '{n} alerta(s)', 'continueChat': 'Continuar — conversa depois conselho',
    'confirmDescribe': 'Confirmar planta/animal e descrever', 'getAdvice': 'Obter conselho',
    'scanChat': 'Conversa', 'message': 'Mensagem…', 'send': 'Enviar', 'voiceNote': 'Nota de voz', 'play': 'Reproduzir',
    'recording': 'A gravar… toque no mic para enviar', 'noMessages': 'Sem mensagens. Diga olá.',
    'videoRequest': 'Pedido de vídeo', 'videoCall': 'Chamada de vídeo', 'voiceCall': 'Chamada',
    'fieldPackReady': 'Pacote pronto neste telefone', 'downloadPacks': 'Descarregue packs antes do campo',
    'downloadRefresh': 'Descarregar / atualizar',
    'chatFirstBanner': 'Conversa primeiro — conselho quando pedir. Funciona offline.',
    'askHost': 'Antes de conselhos: que planta ou animal? Escreva o nome.',
    'askDesc': 'Obrigado. O que vê? Descreva.',
    'howAdvice': 'Para orientação, escreva "conselho" ou "ajuda".',
    'typeAnswer': 'Escreva a resposta…', 'assistant': 'Assistente', 'you': 'Você',
    'savedKb': 'Guardado (especialista aprova tratamentos).',
    'offlineAdvice': 'Orientação offline',
    'noPack': 'Sem guia neste telefone. Ligue-se uma vez ou peça a um técnico.',
    'analyse': 'Analisar', 'extraNotes': 'Notas (opcional)',
    'dangerSigns': 'Sinais de perigo (muitas mortes, sangue, não consegue ficar de pé)',
    'takePhoto': 'Foto', 'chooseGallery': 'Galeria', 'symptoms': 'Sintomas',
    'availableOfficers': 'Especialistas disponíveis', 'noOfficers': 'Nenhum. Registe no portal.',
    'chat': 'Conversa', 'call': 'Ligar', 'district': 'Distrito', 'other': 'Outro',
    'prevention': 'Prevenção / sinais', 'outcome': 'Resultado',
    'packLine': 'Guias: {p} · Especialistas: {e} · Biblioteca: {l}',
    'rememberHost': 'Lembramos que isto é {h}. Pode atualizar o que vê, ou toque Obter conselho.',
    'lastNotes': 'Notas anteriores: {n}',
    'noPackTip': 'Um técnico deve Publicar um procedimento para {h}. Depois Quinta → Atualizar packs online.',
  },

};

String t(String lang, String key) {
  const extra = {
    'reply': {'en': 'Reply', 'ny': 'Yankhani', 'fr': 'Répondre', 'sw': 'Jibu', 'pt': 'Responder'},
    'replyingTo': {'en': 'Replying to', 'ny': 'Mukuyankha', 'fr': 'Réponse à', 'sw': 'Unajibu', 'pt': 'A responder a'},
    'sourceLbl': {'en': 'Source', 'ny': 'Gwero', 'fr': 'Source', 'sw': 'Chanzo', 'pt': 'Fonte'},
    'lookingPhoto': {'en': 'Looking at your photo...', 'ny': "Tikuyang'ana chithunzi chanu...", 'fr': 'Analyse de la photo...', 'sw': 'Tunaangalia picha yako...', 'pt': 'A analisar a foto...'},
    'looksLike': {'en': 'This looks like', 'ny': 'Izi zikuoneka ngati', 'fr': 'Cela ressemble à', 'sw': 'Hii inaonekana kama', 'pt': 'Isto parece'},
    'yesRight': {'en': 'Yes, that is right', 'ny': 'Inde, ndi zolondola', 'fr': "Oui, c'est correct", 'sw': 'Ndiyo, ni sahihi', 'pt': 'Sim, está certo'},
    'chooseOther': {'en': 'No, choose another', 'ny': 'Ayi, sankhani china', 'fr': 'Non, choisir un autre', 'sw': 'Hapana, chagua kingine', 'pt': 'Não, escolher outro'},
    'whatIsThis': {'en': 'What is this?', 'ny': 'Ichi ndi chiyani?', 'fr': "Qu'est-ce que c'est ?", 'sw': 'Hii ni nini?', 'pt': 'O que é isto?'},
    'looksAnimal': {'en': 'This photo looks like an animal. Switch to Livestock?', 'ny': 'Chithunzi ichi chikuoneka ngati chiweto. Sinthani ku Ziweto?', 'fr': 'Cette photo ressemble à un animal. Passer à Animaux ?', 'sw': 'Picha hii inaonekana kama mnyama. Badilisha hadi Mifugo?', 'pt': 'Esta foto parece um animal. Mudar para Animais?'},
    'looksCrop': {'en': 'This photo looks like a plant. Switch to Crops?', 'ny': 'Chithunzi ichi chikuoneka ngati mbewu. Sinthani ku Mbewu?', 'fr': 'Cette photo ressemble à une plante. Passer à Cultures ?', 'sw': 'Picha hii inaonekana kama mmea. Badilisha hadi Mazao?', 'pt': 'Esta foto parece uma planta. Mudar para Culturas?'},
    'switchYes': {'en': 'Switch', 'ny': 'Sinthani', 'fr': 'Changer', 'sw': 'Badilisha', 'pt': 'Mudar'},
    'demoNote': {'en': 'Photo recognition is a demo and not validated. Please confirm what it is.', 'ny': 'Kuzindikira chithunzi ndi koyesera ndipo sikunatsimikizidwe. Chonde tsimikizani chomwe chiri.', 'fr': 'La reconnaissance de photo est une démo non validée. Veuillez confirmer.', 'sw': 'Utambuzi wa picha ni wa majaribio na haujathibitishwa. Tafadhali thibitisha ni nini.', 'pt': 'O reconhecimento de fotos é uma demonstração não validada. Confirme o que é.'},
    'fromBook': {
      'en': 'From published expert library',
      'ny': 'Kuchokera ku buku la akatswiri',
      'fr': 'Bibliothèque publiée',
      'sw': 'Kutoka maktaba iliyochapishwa',
      'pt': 'Biblioteca publicada',
    },
    'askExpertSafe': {
      'en': 'If severe or notifiable, contact a vet or district office.',
      'ny': 'Ngati zoopsa, funani vet.',
      'fr': 'Si grave, contactez un vétérinaire.',
      'sw': 'Ikiwa hatari, wasiliana na daktari wa mifugo.',
      'pt': 'Se grave, contacte um veterinário.',
    },
    'treatment': {
      'en': 'Treatment',
      'ny': 'Chithandizo',
      'fr': 'Traitement',
      'sw': 'Matibabu',
      'pt': 'Tratamento',
    },
  };
  if (extra.containsKey(key)) {
    final m = extra[key]!;
    return m[lang] ?? m['en'] ?? key;
  }
  final Map<String, String>? langMap = ui[lang] is Map
      ? Map<String, String>.from(ui[lang] as Map)
      : null;
  final Map<String, String>? enMap = ui['en'] is Map
      ? Map<String, String>.from(ui['en'] as Map)
      : null;
  final v = langMap?[key] ?? enMap?[key];
  return v ?? key;
}

String tf(String lang, String key, Map<String, String> vars) {
  var s = t(lang, key);
  vars.forEach((k, val) => s = s.replaceAll('{$k}', val));
  return s;
}

String hostLabel(String key, String lang) => hostNames[key]?[lang] ?? hostNames[key]?['en'] ?? key;

const livestockHosts = {'chicken', 'goats', 'cattle', 'pigs', 'sheep', 'ducks', 'goat', 'cow', 'cows'};
const cropHosts = {'maize', 'cassava', 'tomato', 'beans', 'groundnuts', 'rice', 'cabbage', 'other', 'sorghum', 'millet', 'sweet_potato', 'banana', 'onion'};

bool isLivestockHost(String h) {
  final n = h.toLowerCase().trim().replaceAll(RegExp(r'[\s\-]+'), '_');
  return livestockHosts.contains(n);
}

String normalizeHost(String raw) {
  var h = raw.toLowerCase().trim().replaceAll(RegExp(r'[\s\-]+'), '_');
  const aliases = {
    'tomatoes': 'tomato', 'tomatoe': 'tomato', 'nyanya': 'tomato', 'tomate': 'tomato',
    'maize': 'maize', 'corn': 'maize', 'chimanga': 'maize', 'mahindi': 'maize', 'milho': 'maize',
    'cassava': 'cassava', 'chinangwa': 'cassava', 'muhogo': 'cassava',
    'bean': 'beans', 'beans': 'beans',
    'groundnut': 'groundnuts', 'groundnuts': 'groundnuts', 'peanut': 'groundnuts', 'peanuts': 'groundnuts',
    'rice': 'rice', 'mpunga': 'rice',
    'chicken': 'chicken', 'chickens': 'chicken', 'nkhuku': 'chicken', 'poultry': 'chicken',
    'goat': 'goats', 'goats': 'goats', 'mbuzi': 'goats',
    'cow': 'cattle', 'cows': 'cattle', 'cattle': 'cattle', 'ngombe': 'cattle',
  };
  if (aliases.containsKey(h)) return aliases[h]!;
  if (h.endsWith('es') && aliases.containsKey(h.substring(0, h.length - 2))) {
    return aliases[h.substring(0, h.length - 2)]!;
  }
  if (h.endsWith('s') && aliases.containsKey(h.substring(0, h.length - 1))) {
    return aliases[h.substring(0, h.length - 1)]!;
  }
  for (final e in aliases.entries) {
    if (h.contains(e.key) || e.key.contains(h)) return e.value;
  }
  return h;
}

IconData hostIcon(String key) {
  switch (key) {
    case 'maize': return Icons.grass;
    case 'cassava': return Icons.spa;
    case 'tomato': return Icons.eco;
    case 'beans': return Icons.grain;
    case 'groundnuts': return Icons.park;
    case 'rice': return Icons.agriculture;
    case 'chicken': return Icons.egg_alt;
    case 'goats': return Icons.pets;
    case 'cattle': return Icons.cruelty_free;
    case 'other': return Icons.more_horiz;
    default: return Icons.eco;
  }
}

Color hostTint(String key) {
  switch (key) {
    case 'maize': return const Color(0xFFDCFCE7);
    case 'cassava': return const Color(0xFFECFCCB);
    case 'tomato': return const Color(0xFFFFE4E6);
    case 'beans': return const Color(0xFFFEF3C7);
    case 'groundnuts': return const Color(0xFFFFEDD5);
    case 'rice': return const Color(0xFFCCFBF1);
    case 'chicken': return const Color(0xFFFEF9C3);
    case 'goats': return const Color(0xFFF5E6D3);
    case 'cattle': return const Color(0xFFDBEAFE);
    case 'other': return const Color(0xFFECEFF1);
    default: return C.greenSoft;
  }
}

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const App());
}

class App extends StatefulWidget {
  const App({super.key});
  @override
  State<App> createState() => _AppState();
}

class _AppState extends State<App> {
  String lang = 'en';
  String deviceId = '';

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    final p = await SharedPreferences.getInstance();
    var id = p.getString('device_id');
    if (id == null || id.isEmpty) {
      id = const Uuid().v4();
      await p.setString('device_id', id);
    }
    setState(() {
      lang = p.getString('lang') ?? 'en';
      deviceId = id!;
    });
    // Always try pack download after install / open
    await OfflineCache.syncAll(kApiBase).catchError((_) => null);
    await ChatEngine.syncPack(kApiBase).catchError((_) => null);
  }

  Future<void> setLang(String code) async {
    final p = await SharedPreferences.getInstance();
    await p.setString('lang', code);
    setState(() => lang = code);
  }

  @override
  Widget build(BuildContext context) {
    if (deviceId.isEmpty) {
      return MaterialApp(theme: masoTheme(), home: const Scaffold(body: Center(child: CircularProgressIndicator())));
    }
    return MaterialApp(
      title: 'MasoMlimi',
      debugShowCheckedModeBanner: false,
      theme: masoTheme(),
      home: Shell(lang: lang, deviceId: deviceId, onLang: setLang),
    );
  }
}

class Shell extends StatefulWidget {
  final String lang, deviceId;
  final Future<void> Function(String) onLang;
  const Shell({super.key, required this.lang, required this.deviceId, required this.onLang});
  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int tab = 0;
  @override
  Widget build(BuildContext context) {
    final pages = [
      MyFarmPage(lang: widget.lang, deviceId: widget.deviceId, onLang: widget.onLang),
      CheckPage(lang: widget.lang, deviceId: widget.deviceId),
      ExpertsPage(lang: widget.lang),
    ];
    return Scaffold(
      body: pages[tab],
      bottomNavigationBar: NavigationBar(
        selectedIndex: tab,
        onDestinationSelected: (i) => setState(() => tab = i),
        destinations: [
          NavigationDestination(icon: const Icon(Icons.home_outlined), selectedIcon: const Icon(Icons.home), label: t(widget.lang, 'farm')),
          NavigationDestination(icon: const Icon(Icons.camera_alt_outlined), selectedIcon: const Icon(Icons.camera_alt), label: t(widget.lang, 'check')),
          NavigationDestination(icon: const Icon(Icons.groups_outlined), selectedIcon: const Icon(Icons.groups), label: t(widget.lang, 'experts')),
        ],
      ),
    );
  }
}


/// MY FARM — home dashboard matching soft farm mock (greeting, hero, health, quick stats)
class MyFarmPage extends StatefulWidget {
  final String lang, deviceId;
  final Future<void> Function(String) onLang;
  const MyFarmPage({super.key, required this.lang, required this.deviceId, required this.onLang});
  @override
  State<MyFarmPage> createState() => _MyFarmPageState();
}

class _MyFarmPageState extends State<MyFarmPage> {
  List hosts = [];
  List recent = [];
  List alerts = [];
  int publishedCount = 0;
  bool online = false;
  int packProcs = 0;
  int packExperts = 0;
  int packLib = 0;
  String farmName = 'MasoMlimi Farm';

  @override
  void initState() {
    super.initState();
    load();
  }

  String get _greeting {
    final h = DateTime.now().hour;
    if (h < 12) return t(widget.lang, 'greetingMorning');
    if (h < 17) return t(widget.lang, 'greetingAfternoon');
    return t(widget.lang, 'greetingEvening');
  }

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    hosts = jsonDecode(p.getString('farm_hosts') ?? '[]') as List;
    recent = jsonDecode(p.getString('cases') ?? '[]') as List;
    farmName = p.getString('farm_name') ?? 'MasoMlimi Farm';
    try {
      final h = await http.get(Uri.parse('$kApiBase/health')).timeout(const Duration(seconds: 4));
      online = h.statusCode == 200;
      if (online) {
        await OfflineCache.syncAll(kApiBase);
        final sync = await http
            .post(
              Uri.parse('$kApiBase/v1/sync/delta'),
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode({'cursor': 0, 'country': 'MW', 'district': 'Lilongwe'}),
            )
            .timeout(const Duration(seconds: 8));
        if (sync.statusCode == 200) {
          final data = jsonDecode(sync.body) as Map;
          alerts = (data['alerts'] as List?) ?? [];
          final procs = (data['published_procedures'] as List?) ?? [];
          publishedCount = procs.length;
          final sum = data['district_summary'] as Map?;
          if (sum != null && sum['published_procedures'] is int) {
            publishedCount = sum['published_procedures'] as int;
          }
          if (alerts.isNotEmpty) await OfflineCache.saveAlerts(alerts);
          await p.setString('alerts', jsonEncode(alerts));
        }
        await http.put(
          Uri.parse('$kApiBase/v1/farm'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'device_id': widget.deviceId, 'hosts': hosts}),
        );
      } else {
        alerts = await OfflineCache.loadAlerts();
        if (alerts.isEmpty) {
          alerts = jsonDecode(p.getString('alerts') ?? '[]') as List;
        }
      }
    } catch (_) {
      online = false;
      alerts = await OfflineCache.loadAlerts();
      if (alerts.isEmpty) {
        alerts = jsonDecode(p.getString('alerts') ?? '[]') as List;
      }
    }
    final pack = await OfflineCache.packSummary();
    packProcs = pack['procedures'] ?? 0;
    packExperts = pack['experts'] ?? 0;
    packLib = pack['library'] ?? 0;
    if (publishedCount == 0) publishedCount = packProcs;
    if (mounted) setState(() {});
  }

  Future<void> addHost(String key, String organism) async {
    final c = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(hostLabel(key, widget.lang)),
        content: TextField(controller: c, decoration: InputDecoration(labelText: t(widget.lang, 'period'))),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(t(widget.lang, 'cancel'))),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text(t(widget.lang, 'save'))),
        ],
      ),
    );
    if (ok != true) return;
    hosts = [
      ...hosts.where((h) => '${h['host_key']}' != key),
      {'host_key': key, 'organism_type': organism, 'period': c.text.trim().isEmpty ? 'This season' : c.text.trim()},
    ];
    final p = await SharedPreferences.getInstance();
    await p.setString('farm_hosts', jsonEncode(hosts));
    setState(() {});
    load();
  }

  Future<void> _renameFarm() async {
    final c = TextEditingController(text: farmName);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(t(widget.lang, 'farmName')),
        content: TextField(controller: c, decoration: const InputDecoration(hintText: 'e.g. Green Valley Farm')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(t(widget.lang, 'cancel'))),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text(t(widget.lang, 'save'))),
        ],
      ),
    );
    if (ok == true && c.text.trim().isNotEmpty) {
      final p = await SharedPreferences.getInstance();
      await p.setString('farm_name', c.text.trim());
      setState(() => farmName = c.text.trim());
    }
  }

  int get _cropCount => hosts.where((h) => '${h['organism_type']}' != 'livestock').length;
  int get _animalCount => hosts.where((h) => '${h['organism_type']}' == 'livestock').length;

  /// Simple farm health score from packs + alerts (not a medical claim).
  double get _healthScore {
    if (packProcs <= 0 && hosts.isEmpty) return 0.55;
    final alertPenalty = (alerts.length * 0.08).clamp(0.0, 0.35);
    final base = hosts.isEmpty ? 0.7 : 0.88;
    return (base - alertPenalty).clamp(0.4, 0.98);
  }

  String get _healthLabel {
    final s = _healthScore;
    if (alerts.isNotEmpty) return widget.lang == 'ny' ? 'Yang\'anirani' : 'Check alerts';
    if (s >= 0.85) return widget.lang == 'ny' ? 'Bwino' : 'Healthy';
    if (s >= 0.65) return 'OK';
    return widget.lang == 'ny' ? 'Osamalitsa' : 'Needs care';
  }

  @override
  Widget build(BuildContext context) {
    final healthPct = (_healthScore * 100).round();
    return Scaffold(
      backgroundColor: const Color(0xFFF3F7F4),
      body: RefreshIndicator(
        onRefresh: load,
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            SliverToBoxAdapter(
              child: SafeArea(
                bottom: false,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Header: avatar + greeting + farm + bell
                      Row(
                        children: [
                          CircleAvatar(
                            radius: 24,
                            backgroundColor: C.greenSoft,
                            child: Icon(Icons.person, color: C.greenDark),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '$_greeting',
                                  style: TextStyle(fontSize: 13, color: Colors.grey.shade600, fontWeight: FontWeight.w500),
                                ),
                                GestureDetector(
                                  onTap: _renameFarm,
                                  child: Row(
                                    children: [
                                      Flexible(
                                        child: Text(
                                          farmName,
                                          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: Color(0xFF1F2937)),
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ),
                                      Icon(Icons.keyboard_arrow_down, color: Colors.grey.shade700),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            onPressed: load,
                            style: IconButton.styleFrom(backgroundColor: Colors.white),
                            icon: Icon(online ? Icons.notifications_none : Icons.cloud_off, color: C.greenDark),
                          ),
                          PopupMenuButton<String>(
                            icon: const Icon(Icons.language, color: C.greenDark),
                            onSelected: widget.onLang,
                            itemBuilder: (_) => const [
                              PopupMenuItem(value: 'en', child: Text('English')),
                              PopupMenuItem(value: 'ny', child: Text('Chichewa')),
                              PopupMenuItem(value: 'fr', child: Text('Français')),
                              PopupMenuItem(value: 'sw', child: Text('Kiswahili')),
                              PopupMenuItem(value: 'pt', child: Text('Português')),
                            ],
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Hero illustration card
                      Container(
                        width: double.infinity,
                        height: 150,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(24),
                          gradient: const LinearGradient(
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                            colors: [Color(0xFFB8E4C9), Color(0xFF7BC896), Color(0xFF5BB87A)],
                          ),
                          boxShadow: [
                            BoxShadow(color: C.greenDark.withValues(alpha: 0.15), blurRadius: 16, offset: const Offset(0, 8)),
                          ],
                        ),
                        child: Stack(
                          children: [
                            Positioned(
                              right: 12,
                              top: 16,
                              child: Icon(Icons.wb_sunny_rounded, color: Colors.amber.shade200, size: 36),
                            ),
                            Positioned(
                              left: 20,
                              bottom: 16,
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Icon(Icons.agriculture, color: Colors.white.withValues(alpha: 0.95), size: 48),
                                  const SizedBox(width: 8),
                                  Icon(Icons.cottage_outlined, color: Colors.white.withValues(alpha: 0.9), size: 40),
                                  const SizedBox(width: 6),
                                  Icon(Icons.pets, color: Colors.white.withValues(alpha: 0.85), size: 28),
                                ],
                              ),
                            ),
                            Positioned(
                              right: 20,
                              bottom: 20,
                              child: Icon(Icons.eco, color: Colors.white.withValues(alpha: 0.5), size: 64),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 16),

                      // Farm Health + Status row
                      Row(
                        children: [
                          Expanded(
                            child: _softCard(
                              child: Row(
                                children: [
                                  SizedBox(
                                    width: 56,
                                    height: 56,
                                    child: Stack(
                                      alignment: Alignment.center,
                                      children: [
                                        CircularProgressIndicator(
                                          value: _healthScore,
                                          strokeWidth: 6,
                                          backgroundColor: const Color(0xFFE5E7EB),
                                          color: alerts.isEmpty ? C.greenDark : C.amber,
                                        ),
                                        Text('$healthPct%', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12)),
                                      ],
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(t(widget.lang, 'farmHealth'), style: TextStyle(fontSize: 12, color: Colors.grey.shade600, fontWeight: FontWeight.w600)),
                                        Text(_healthLabel, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800)),
                                        Text(
                                          alerts.isEmpty ? (online ? t(widget.lang, 'allGood') : t(widget.lang, 'offlinePack')) : tf(widget.lang, 'alertN', {'n': '${alerts.length}'}),
                                          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _softCard(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Icon(online ? Icons.cloud_done : Icons.cloud_off, color: C.greenDark, size: 22),
                                      const SizedBox(width: 6),
                                      Text(online ? t(widget.lang, 'online') : t(widget.lang, 'offline'), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                                    ],
                                  ),
                                  const SizedBox(height: 6),
                                  Text(tf(widget.lang, 'guidesOfficers', {'p': '$packProcs', 'e': '$packExperts'}), style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
                                  Text(tf(widget.lang, 'libraryN', {'n': '$packLib'}), style: TextStyle(fontSize: 11, color: Colors.grey.shade600)),
                                  TextButton(
                                    style: TextButton.styleFrom(padding: EdgeInsets.zero, minimumSize: const Size(0, 28)),
                                    onPressed: load,
                                    child: Text(t(widget.lang, 'refreshPacks')),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 22),

                      Text(t(widget.lang, 'quickStats'), style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Colors.grey.shade800)),
                      const SizedBox(height: 12),
                      GridView.count(
                        crossAxisCount: 2,
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        mainAxisSpacing: 12,
                        crossAxisSpacing: 12,
                        childAspectRatio: 1.35,
                        children: [
                          _statTile(Icons.grass, '$_cropCount', t(widget.lang, 'crops'), const Color(0xFFDCFCE7)),
                          _statTile(Icons.pets, '$_animalCount', t(widget.lang, 'animals'), const Color(0xFFFFF3E0)),
                          _statTile(Icons.menu_book, '$packProcs', t(widget.lang, 'guides'), const Color(0xFFE0F2FE)),
                          _statTile(Icons.history, '${recent.length}', t(widget.lang, 'scans'), const Color(0xFFF3E8FF)),
                        ],
                      ),
                      const SizedBox(height: 22),

                      // Add crops / animals (keep function, soft UI)
                      Text(t(widget.lang, 'myCropsAnimals'), style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Colors.grey.shade800)),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final k in ['maize', 'cassava', 'tomato', 'beans', 'groundnuts', 'rice'])
                            ActionChip(
                              avatar: CircleAvatar(
                                backgroundColor: Colors.transparent,
                                backgroundImage: AssetImage('assets/hosts/$k.png'),
                                onBackgroundImageError: (_, __) {},
                              ),
                              label: Text(hostLabel(k, widget.lang)),
                              backgroundColor: Colors.white,
                              onPressed: () => addHost(k, 'crop'),
                            ),
                          for (final k in ['chicken', 'goats', 'cattle'])
                            ActionChip(
                              avatar: CircleAvatar(
                                backgroundColor: Colors.transparent,
                                backgroundImage: AssetImage('assets/hosts/$k.png'),
                                onBackgroundImageError: (_, __) {},
                              ),
                              label: Text(hostLabel(k, widget.lang)),
                              backgroundColor: Colors.white,
                              onPressed: () => addHost(k, 'livestock'),
                            ),
                        ],
                      ),
                      if (hosts.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        ...hosts.map((h) {
                          final key = '${h['host_key']}';
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: _softCard(
                              child: Row(
                                children: [
                                  CircleAvatar(
                                    backgroundColor: hostTint(key),
                                    backgroundImage: AssetImage('assets/hosts/$key.png'),
                                    onBackgroundImageError: (_, __) {},
                                  ),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(hostLabel(key, widget.lang), style: const TextStyle(fontWeight: FontWeight.w700)),
                                        Text('${h['period'] ?? ''}', style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          );
                        }),
                      ],
                      if (alerts.isNotEmpty) ...[
                        const SizedBox(height: 16),
                        Text(t(widget.lang, 'alerts'), style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: Colors.grey.shade800)),
                        const SizedBox(height: 8),
                        ...alerts.take(5).map((a) {
                          final title = a is Map ? '${a['title'] ?? a['message'] ?? a}' : '$a';
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: _softCard(
                              child: Row(
                                children: [
                                  Icon(Icons.warning_amber_rounded, color: Colors.orange.shade700),
                                  const SizedBox(width: 10),
                                  Expanded(child: Text(title, style: const TextStyle(fontWeight: FontWeight.w600))),
                                ],
                              ),
                            ),
                          );
                        }),
                      ],
                      const SizedBox(height: 28),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _softCard({required Widget child}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 12, offset: const Offset(0, 4)),
        ],
      ),
      child: child,
    );
  }

  Widget _statTile(IconData icon, String value, String label, Color bg) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 12, offset: const Offset(0, 4)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(12)),
            child: Icon(icon, color: C.greenDark, size: 20),
          ),
          const Spacer(),
          Text(value, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
          Text(label, style: TextStyle(fontSize: 13, color: Colors.grey.shade600, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}

class ResultPage extends StatefulWidget {
  final String lang, deviceId, hostKey, organismHint;
  final String? photoPath;
  final List<String> symptomKeys;
  final bool dangerSigns;
  final String notes;
  const ResultPage({
    super.key,
    required this.lang,
    required this.deviceId,
    required this.hostKey,
    required this.organismHint,
    this.photoPath,
    this.symptomKeys = const [],
    this.dangerSigns = false,
    this.notes = '',
  });
  @override
  State<ResultPage> createState() => _ResultPageState();
}

class _ResultPageState extends State<ResultPage> {
  bool loading = true;
  Map<String, dynamic>? result;
  String? errorLine;
  String lastUrl = '';

  @override
  void initState() {
    super.initState();
    run();
  }

  Map<String, dynamic>? _asMap(dynamic v) {
    if (v is Map<String, dynamic>) return v;
    if (v is Map) return Map<String, dynamic>.from(v);
    return null;
  }

  List _asList(dynamic v) {
    if (v is List) return v;
    return const [];
  }

  Future<void> run({bool danger = false}) async {
    setState(() {
      loading = true;
      errorLine = null;
    });
    lastUrl = '$kApiBase/v1/diagnosis/diagnose';
    try {
      http.Response res;
      if (widget.photoPath != null) {
        lastUrl = '$kApiBase/v1/scan/analyze';
        final req = http.MultipartRequest('POST', Uri.parse(lastUrl));
        req.fields['host_key'] = widget.hostKey;
        req.fields['organism_hint'] = widget.organismHint;
        req.fields['language'] = widget.lang;
        req.fields['device_id'] = widget.deviceId;
        req.fields['danger_signs_present'] = (danger || widget.dangerSigns).toString();
        req.files.add(await http.MultipartFile.fromPath('image', widget.photoPath!));
        final streamed = await req.send().timeout(const Duration(seconds: 30));
        res = await http.Response.fromStream(streamed);
      } else {
        res = await http
            .post(
              Uri.parse(lastUrl),
              headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
              body: jsonEncode({
                'host_key': widget.hostKey,
                'organism_hint': widget.organismHint,
                'danger_signs_present': danger || widget.dangerSigns,
                'symptom_keys': widget.symptomKeys,
                'answers': widget.notes.isEmpty ? {} : {'notes': widget.notes},
                'language': widget.lang,
                'device_id': widget.deviceId,
              }),
            )
            .timeout(const Duration(seconds: 15));
      }
      if (res.statusCode != 200) {
        setState(() {
          errorLine = 'HTTP ${res.statusCode}: ${res.body}';
          result = {
            'outcome': 'not_sure',
            'result_color': 'red',
            'messages': {'primary': 'Server error ${res.statusCode}', 'ask_expert_note': t(widget.lang, 'callExpert')},
            'procedure_steps': [],
          };
        });
        return;
      }
      final decoded = jsonDecode(res.body);
      final data = _asMap(decoded) ?? <String, dynamic>{};
      setState(() => result = data);
      // Refresh procedure pack in background for next offline use
      try {
        final pr = await http.get(Uri.parse('$kApiBase/v1/procedures')).timeout(const Duration(seconds: 6));
        if (pr.statusCode == 200) {
          final pdata = jsonDecode(pr.body);
          final items = pdata is Map ? (pdata['items'] as List? ?? []) : [];
          await OfflineCache.saveProcedures(items);
          await OfflineCache.flushOutbox(kApiBase);
        }
      } catch (_) {}

      final cond = _asMap(data['condition']);
      final title = '${cond?['common_name'] ?? data['outcome'] ?? ''}';
      final p = await SharedPreferences.getInstance();
      final cases = jsonDecode(p.getString('cases') ?? '[]') as List;
      cases.insert(0, {
        'host_key': widget.hostKey,
        'outcome': data['outcome'],
        'color': data['result_color'],
        'title': title,
        'at': DateTime.now().toIso8601String(),
      });
      await p.setString('cases', jsonEncode(cases.take(40).toList()));
    } catch (e) {
      // Offline: use last downloaded published procedures
      final cached = await OfflineCache.loadProcedures();
      final matched = OfflineCache.matchPublished(cached, widget.hostKey, widget.symptomKeys);
      if (matched != null) {
        setState(() {
          errorLine = 'Offline — showing saved expert guidance';
          result = OfflineCache.resultFromProcedure(matched, widget.lang);
        });
      } else {
        setState(() {
          errorLine = 'Offline and no saved guidance for this crop/animal yet. Open app online once to download.';
          result = {
            'outcome': 'not_sure',
            'result_color': 'red',
            'messages': {
              'primary': 'No offline pack for this host. Connect once to download published guides.',
              'ask_expert_note': t(widget.lang, 'callExpert'),
            },
            'procedure_steps': [],
          };
        });
      }
    } finally {
      setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final steps = _asList(result?['procedure_steps']);
    final prevention = _asList(result?['prevention_steps']);
    final cond = _asMap(result?['condition']);
    final msgs = _asMap(result?['messages']);
    final name = '${cond?['common_name'] ?? hostLabel(widget.hostKey, widget.lang)}';
    final primary = '${msgs?['primary'] ?? ''}';
    final published = result?['from_published_library'] == true;
    final outcome = '${result?['outcome'] ?? ''}';

    return Scaffold(
      appBar: AppBar(
        title: Text(t(widget.lang, 'result')),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: () => run()),
        ],
      ),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // Always show connection status so farmers/dev can see if API was hit
                DashCard(
                  color: published ? C.greenSoft : (errorLine != null ? C.redSoft : C.amberSoft),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        published
                            ? 'Expert-published guidance'
                            : (errorLine != null ? 'Could not load from server' : 'Result'),
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 4),
                      Text('API: $kApiBase', style: const TextStyle(fontSize: 11, color: C.muted)),
                      if (outcome.isNotEmpty) Text('${t(widget.lang, 'outcome')}: $outcome', style: const TextStyle(fontSize: 12)),
                      if (errorLine != null) Text(errorLine!, style: const TextStyle(fontSize: 12, color: C.red)),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                if (widget.photoPath != null)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(16),
                    child: Image.file(File(widget.photoPath!), height: 160, width: double.infinity, fit: BoxFit.cover),
                  ),
                const SizedBox(height: 12),
                Text(t(widget.lang, 'likely'), style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 8),
                SoftListCard(
                  leading: Icon(hostIcon(widget.hostKey), color: C.greenDark),
                  leadingBg: hostTint(widget.hostKey),
                  title: name,
                  subtitle: hostLabel(widget.hostKey, widget.lang),
                  trailing: const SizedBox.shrink(),
                ),
                if (primary.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(primary, style: const TextStyle(height: 1.35)),
                ],
                if (msgs?['published_note'] != null) ...[
                  const SizedBox(height: 6),
                  Text('${msgs!['published_note']}', style: const TextStyle(fontSize: 12, color: C.muted)),
                ],
                const SizedBox(height: 14),
                Text(t(widget.lang, 'cando'), style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 8),
                if (steps.isEmpty)
                  SoftListCard(
                    leading: const Icon(Icons.support_agent, color: C.greenDark),
                    title: '${msgs?['ask_expert_note'] ?? t(widget.lang, 'callExpert')}',
                    trailing: const SizedBox.shrink(),
                  )
                else
                  ...steps.map((s) {
                    String text;
                    if (s is Map) {
                      text = '${s['text'] ?? s}';
                    } else {
                      text = '$s';
                    }
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: SoftListCard(
                        leading: const Icon(Icons.check_circle_outline, color: C.greenDark),
                        title: text,
                        trailing: const SizedBox.shrink(),
                      ),
                    );
                  }),
                if (prevention.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Text(t(widget.lang, 'prevention'), style: const TextStyle(fontWeight: FontWeight.w800)),
                  const SizedBox(height: 8),
                  ...prevention.map((s) {
                    final text = s is Map ? '${s['text'] ?? s}' : '$s';
                    if (text.startsWith('Sign:')) {
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: SoftListCard(
                          leading: const Icon(Icons.visibility_outlined, color: C.amber),
                          title: text.replaceFirst('Sign: ', ''),
                          trailing: const SizedBox.shrink(),
                        ),
                      );
                    }
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: SoftListCard(
                        leading: const Icon(Icons.shield_outlined, color: C.greenDark),
                        title: text,
                        trailing: const SizedBox.shrink(),
                      ),
                    );
                  }),
                ],
                if (widget.organismHint == 'livestock') ...[
                  const SizedBox(height: 8),
                  OutlinedButton(onPressed: () => run(danger: true), child: Text(t(widget.lang, 'danger'))),
                ],
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: () {
                    final outcome = '${result?['outcome'] ?? ''}';
                    Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => KnowledgeChatPage(
                        lang: widget.lang,
                        deviceId: widget.deviceId,
                        hostKey: widget.hostKey,
                        organismType: widget.organismHint,
                        scanOutcome: outcome,
                      ),
                    ));
                  },
                  icon: const Icon(Icons.chat_bubble_outline),
                  label: Text(t(widget.lang, 'confirmDescribe')),
                ),
                const SizedBox(height: 8),
                FilledButton.icon(
                  onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => ExpertsPage(lang: widget.lang))),
                  icon: const Icon(Icons.phone),
                  label: Text(t(widget.lang, 'callExpert')),
                ),
              ],
            ),
    );
  }
}


class ExpertsPage extends StatefulWidget {
  final String lang;
  const ExpertsPage({super.key, required this.lang});
  @override
  State<ExpertsPage> createState() => _ExpertsPageState();
}

class _ExpertsPageState extends State<ExpertsPage> {
  List experts = [];
  String deviceId = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final p = await SharedPreferences.getInstance();
    deviceId = p.getString('device_id') ?? '';
    // Instant offline paint
    final cached = await OfflineCache.loadExperts();
    if (mounted && cached.isNotEmpty) setState(() => experts = cached);
    List loaded = [];
    try {
      for (final q in ['district=all', 'district=Dowa', 'district=Lilongwe', '']) {
        final url = q.isEmpty ? '$kApiBase/v1/experts/' : '$kApiBase/v1/experts/?country=MW&$q';
        final res = await http.get(Uri.parse(url)).timeout(const Duration(seconds: 6));
        if (res.statusCode == 200) {
          final data = jsonDecode(res.body);
          if (data is List && data.isNotEmpty) {
            loaded = data;
            break;
          }
        }
      }
    } catch (_) {}
    if (loaded.isNotEmpty) {
      await OfflineCache.saveExperts(loaded);
      if (mounted) setState(() => experts = loaded);
    } else if (mounted && experts.isEmpty) {
      setState(() => experts = cached);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(t(widget.lang, 'experts')),
        actions: [IconButton(icon: const Icon(Icons.refresh), onPressed: _load)],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(t(widget.lang, 'availableOfficers'), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
          const SizedBox(height: 4),
          const Text('Chat, voice or video with verified district staff.', style: TextStyle(color: C.muted, fontSize: 13)),
          const SizedBox(height: 12),
          if (experts.isEmpty)
            const DashCard(
              child: Text(
                'No officers registered yet. District staff must add their names in the Expert Portal (Officers tab).',
                style: TextStyle(color: C.muted, height: 1.35),
              ),
            )
          else
          ...experts.map((e) {
            final name = '${e['display_name']}';
            final role = '${e['role_label'] ?? ''}';
            final avail = '${e['availability'] ?? ''}';
            final id = '${e['id'] ?? name}';
            final phone = e['phone_e164'];
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: DashCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        CircleAvatar(
                          backgroundColor: C.greenSoft,
                          child: Text(name.isNotEmpty ? name[0] : '?', style: const TextStyle(color: C.greenDark, fontWeight: FontWeight.w800)),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(name, style: const TextStyle(fontWeight: FontWeight.w800)),
                              Text('$role · ${e['district'] ?? ''}', style: const TextStyle(color: C.muted, fontSize: 12)),
                              Text(avail, style: TextStyle(color: avail == 'available' ? C.greenDark : C.muted, fontSize: 12, fontWeight: FontWeight.w600)),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: FilledButton.icon(
                            onPressed: () {
                              Navigator.of(context).push(MaterialPageRoute(
                                builder: (_) => ExpertChatPage(
                                  lang: widget.lang,
                                  deviceId: deviceId,
                                  expertId: id,
                                  expertName: name,
                                  expertRole: role,
                                  phone: phone is String ? phone : null,
                                ),
                              ));
                            },
                            icon: const Icon(Icons.chat_bubble_outline, size: 18),
                            label: const Text('Chat'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: phone != null
                                ? () => launchUrl(Uri.parse('tel:$phone'))
                                : () {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(content: Text('Phone number not listed — use Chat or office hours')),
                                    );
                                  },
                            icon: const Icon(Icons.call, size: 18),
                            label: const Text('Call'),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            );
          }),
          SoftListCard(
            leading: const Icon(Icons.account_balance, color: C.greenDark),
            title: 'District agriculture office',
            subtitle: 'General enquiries and support',
            trailing: const SizedBox.shrink(),
          ),
        ],
      ),
    );
  }
}

/// Post-scan: chat first; guidance only when farmer asks for advice (online + offline).

