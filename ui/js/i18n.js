/* LinguaDocs i18n — traductions de l'interface (en/fr/es/ar). */
const isRTL = (lang) => lang === 'ar';

const translations = {
  app_title: {
    en: 'LinguaDocs',
    fr: 'LinguaDocs',
    es: 'LinguaDocs',
    ar: 'لينغوادوكس',
  },
  app_tagline: {
    en: 'Multilingual Local RAG Document Assistant',
    fr: 'Assistant documentaire RAG local multilingue',
    es: 'Asistente documental RAG local multilingüe',
    ar: 'المساعد الوثائقي الذكي متعدد اللغات بتقنية RAG المحلية',
  },
  theme_dark: { en: 'Dark Mode', fr: 'Mode sombre', es: 'Modo oscuro', ar: 'الوضع الداكن' },
  theme_light: { en: 'Light Mode', fr: 'Mode clair', es: 'Modo claro', ar: 'الوضع الفاتح' },
  language: { en: 'Language', fr: 'Langue', es: 'Idioma', ar: 'اللغة' },
  logout: { en: 'Log Out', fr: 'Déconnexion', es: 'Cerrar sesión', ar: 'تسجيل الخروج' },
  account: { en: 'Account Settings', fr: 'Paramètres du compte', es: 'Configuración de cuenta', ar: 'إعدادات الحساب' },
  close: { en: 'Close', fr: 'Fermer', es: 'Cerrar', ar: 'إغلاق' },
  cancel: { en: 'Cancel', fr: 'Annuler', es: 'Cancelar', ar: 'إلغاء' },
  confirm: { en: 'Confirm', fr: 'Confirmer', es: 'Confirmar', ar: 'تأكيد' },
  refresh: { en: 'Refresh', fr: 'Actualiser', es: 'Actualizar', ar: 'تحديث' },
  delete: { en: 'Delete', fr: 'Supprimer', es: 'Eliminar', ar: 'حذف' },
  copy: { en: 'Copy', fr: 'Copier', es: 'Copiar', ar: 'نسخ' },
  copied: { en: 'Copied!', fr: 'Copié !', es: '¡Copiado!', ar: 'تم النسخ!' },
  save: { en: 'Save', fr: 'Enregistrer', es: 'Guardar', ar: 'حفظ' },

  // Auth
  auth_login_tab: { en: 'Sign In', fr: 'Connexion', es: 'Iniciar Sesión', ar: 'تسجيل الدخول' },
  auth_register_tab: { en: 'Create Account', fr: 'Créer un compte', es: 'Crear Cuenta', ar: 'إنشاء حساب' },
  auth_email: { en: 'Email Address', fr: 'Adresse e-mail', es: 'Correo electrónico', ar: 'البريد الإلكتروني' },
  auth_email_placeholder: { en: 'you@domain.com', fr: 'vous@domaine.com', es: 'usuario@correo.com', ar: 'you@domain.com' },
  auth_password: { en: 'Password', fr: 'Mot de passe', es: 'Contraseña', ar: 'كلمة المرور' },
  auth_password_confirm: { en: 'Confirm Password', fr: 'Confirmer le mot de passe', es: 'Confirmar Contraseña', ar: 'تأكيد كلمة المرور' },
  auth_password_hint: {
    en: 'Must be at least 8 characters.',
    fr: 'Doit contenir au moins 8 caractères.',
    es: 'Debe tener al menos 8 caracteres.',
    ar: 'يجب أن تحتوي على 8 أحرف على الأقل.',
  },
  auth_btn_login: { en: 'Sign In to LinguaDocs', fr: 'Se connecter à LinguaDocs', es: 'Iniciar Sesión en LinguaDocs', ar: 'تسجيل الدخول إلى لينغوادوكس' },
  auth_btn_register: { en: 'Create Free Account', fr: 'Créer un compte gratuit', es: 'Crear Cuenta Gratuita', ar: 'إنشاء حساب جديد' },
  auth_err_email_invalid: { en: 'Please enter a valid email address.', fr: 'Veuillez entrer une adresse e-mail valide.', es: 'Por favor ingrese un correo válido.', ar: 'يرجى إدخال عنوان بريد إلكتروني صحيح.' },
  auth_err_password_len: { en: 'Password must be at least 8 characters long.', fr: 'Le mot de passe doit comporter au moins 8 caractères.', es: 'La contraseña debe tener al menos 8 caracteres.', ar: 'يجب ألا تقل كلمة المرور عن 8 أحرف.' },
  auth_err_password_mismatch: { en: 'Passwords do not match.', fr: 'Les mots de passe ne correspondent pas.', es: 'Las contraseñas no coinciden.', ar: 'كلمتا المرور غير متطابقتين.' },
  auth_success_registered: { en: 'Account created successfully. Please sign in.', fr: 'Compte créé avec succès. Veuillez vous connecter.', es: 'Cuenta creada con éxito. Inicie sesión.', ar: 'تم إنشاء الحساب بنجاح. يرجى تسجيل الدخول.' },
  auth_delete_account: { en: 'Delete Account', fr: 'Supprimer le compte', es: 'Eliminar Cuenta', ar: 'حذف الحساب' },
  auth_delete_warning: {
    en: 'This will permanently delete your user account and all indexed documents. Type DELETE to confirm.',
    fr: 'Cela supprimera définitivement votre compte et tous vos documents indexés. Tapez DELETE pour confirmer.',
    es: 'Esto eliminará permanentemente su cuenta y todos los documentos indexados. Escriba DELETE para confirmar.',
    ar: 'سيؤدي هذا إلى حذف حسابك وجميع المستندات المفهرسة نهائيًا. اكتب DELETE للتأكيد.',
  },

  // Document Sidebar
  docs_title: { en: 'Documents', fr: 'Documents', es: 'Documentos', ar: 'المستندات' },
  docs_upload_btn: { en: 'Upload Document', fr: 'Téléverser un document', es: 'Subir Documento', ar: 'رفع مستند' },
  docs_search_placeholder: { en: 'Search documents...', fr: 'Rechercher des documents...', es: 'Buscar documentos...', ar: 'البحث في المستندات...' },
  docs_no_documents: { en: 'No documents uploaded yet.', fr: 'Aucun document téléversé pour l\'instant.', es: 'No hay documentos aún.', ar: 'لا توجد مستندات مرفوعة بعد.' },
  docs_no_match: { en: 'No documents match your search.', fr: 'Aucun document ne correspond à votre recherche.', es: 'Ningún documento coincide con la búsqueda.', ar: 'لا توجد نتائج مطابقة لبحثك.' },
  docs_status_queued: { en: 'Queued', fr: 'En file d\'attente', es: 'En cola', ar: 'في الانتظار' },
  docs_status_processing: { en: 'Processing', fr: 'Traitement en cours', es: 'Procesando', ar: 'قيد المعالجة' },
  docs_status_indexed: { en: 'Indexed', fr: 'Indexé', es: 'Indexado', ar: 'تمت الفهرسة' },
  docs_status_error: { en: 'Error', fr: 'Erreur', es: 'Error', ar: 'خطأ' },
  docs_delete_confirm: { en: 'Delete this document?', fr: 'Supprimer ce document ?', es: '¿Eliminar este documento?', ar: 'هل تريد حذف هذا المستند؟' },

  // Welcome View
  welcome_heading: { en: 'Welcome to LinguaDocs', fr: 'Bienvenue sur LinguaDocs', es: 'Bienvenido a LinguaDocs', ar: 'مرحبًا بك في لينغوادوكس' },
  welcome_subheading: {
    en: 'Your local, privacy-first multilingual RAG assistant. Grounded answers, accurate page citations, quizzes, and summaries.',
    fr: 'Votre assistant RAG local et confidentiel. Réponses étayées, citations précises, quiz et synthèses.',
    es: 'Tu asistente RAG local centrado en la privacidad. Respuestas fundamentadas, citas de páginas, cuestionarios y resúmenes.',
    ar: 'مساعدك الوثائقي المحلي المدعوم بنماذج الذكاء الاصطناعي مع الحفاظ التام على الخصوصية، إجابات دقيقة موثقة بالمصادر، تلخيص واختبارات.',
  },
  welcome_upload_cta: { en: 'Upload your first document to start querying', fr: 'Téléversez votre premier document pour commencer', es: 'Sube tu primer documento para comenzar', ar: 'قم برفع مستندك الأول للبدء في الاستفسار' },
  welcome_supported_formats: { en: 'Supported formats: PDF, TXT, Markdown, DOCX (up to 50MB)', fr: 'Formats acceptés : PDF, TXT, Markdown, DOCX (jusqu\'à 50 Mo)', es: 'Formatos admitidos: PDF, TXT, Markdown, DOCX (hasta 50MB)', ar: 'الصيغ المدعومة: PDF, TXT, Markdown, DOCX (حتى 50 ميغابايت)' },
  welcome_example_questions_title: { en: 'What you can ask once a document is indexed:', fr: 'Ce que vous pouvez demander une fois le document indexé :', es: 'Lo que puedes preguntar una vez indexado el documento:', ar: 'أمثلة على ما يمكنك طرحه بمجرد فهرسة المستند:' },
  welcome_eg1: { en: 'Summarize the primary methodology and key findings in Chapter 2.', fr: 'Résumez la méthodologie principale et les conclusions clés du chapitre 2.', es: 'Resume la metodología principal y los hallazgos clave del capítulo 2.', ar: 'لخّص المنهجية الأساسية والنتائج الرئيسية في الفصل الثاني.' },
  welcome_eg2: { en: 'What are the limitations or constraints outlined by the authors?', fr: 'Quelles sont les limites ou contraintes exposées par les auteurs ?', es: '¿Cuáles son las limitaciones o restricciones señaladas por los autores?', ar: 'ما هي القيود والمحددات التي ذكرها المؤلفون؟' },
  welcome_eg3: { en: 'Compare the conclusions with the prior baseline studies mentioned.', fr: 'Comparez les conclusions avec les études de référence mentionnées.', es: 'Compara las conclusiones con los estudios de referencia citados.', ar: 'قارن بين الاستنتاجات والدراسات السابقة المرجعية المذكورة.' },

  // Chat Workspace
  chat_placeholder: { en: 'Ask a question about this document...', fr: 'Posez une question sur ce document...', es: 'Haz una pregunta sobre este documento...', ar: 'اطرح سؤالاً حول هذا المستند...' },
  chat_send: { en: 'Ask', fr: 'Envoyer', es: 'Preguntar', ar: 'إرسال' },
  chat_stop: { en: 'Stop Generating', fr: 'Arrêter la génération', es: 'Detener generación', ar: 'إيقاف التوليد' },
  chat_clear: { en: 'Clear Conversation', fr: 'Effacer la conversation', es: 'Limpiar conversación', ar: 'مسح المحادثة' },
  chat_model_warming: {
    en: 'Local model is warming up, the first token may take a few seconds...',
    fr: 'Le modèle local chauffe, le premier jeton peut prendre quelques secondes...',
    es: 'El modelo local se está inicializando, el primer token puede demorar unos segundos...',
    ar: 'النموذج المحلي قيد التهيئة، قد يستغرق الرمز الأول بضع ثوانٍ...',
  },
  chat_refusal_banner: {
    en: 'The retrieval score is below 0.30. I don\'t have enough grounded evidence in your document to answer this safely.',
    fr: 'Le score de récupération est inférieur à 0,30. Je n\'ai pas suffisamment de preuves fiables dans votre document pour répondre.',
    es: 'La puntuación de recuperación es inferior a 0,30. No hay suficiente evidencia en el documento para responder con certeza.',
    ar: 'درجة مطابقة الاسترجاع أقل من 0.30. لا تتوفر أدلة كافية وموثقة في المستند للإجابة بشكل دقيق.',
  },
  chat_sources_label: { en: 'Grounded Sources:', fr: 'Sources référencées :', es: 'Fuentes citadas:', ar: 'المصادر المعتمدة:' },
  chat_latency: { en: 'Latency', fr: 'Latence', es: 'Latencia', ar: 'زمن الاستجابة' },

  // Document Viewer
  viewer_title: { en: 'Document Inspector', fr: 'Inspecteur de document', es: 'Inspector de documento', ar: 'معاين المستند' },
  viewer_chunk: { en: 'Chunk', fr: 'Segment', es: 'Fragmento', ar: 'المقطع' },
  viewer_page: { en: 'Page', fr: 'Page', es: 'Página', ar: 'الصفحة' },
  viewer_score: { en: 'Score', fr: 'Score', es: 'Puntuación', ar: 'درجة التطابق' },
  viewer_no_source: { en: 'Click on any citation (e.g. filename · p.1) to view and highlight the exact grounded chunk here.', fr: 'Cliquez sur une citation (ex. nom_fichier · p.1) pour inspecter le segment surligné.', es: 'Haga clic en una cita (ej. archivo · p.1) para inspeccionar el fragmento.', ar: 'انقر على أي استشهاد (مثل: اسم_الملف · ص.1) لمعاينة المقطع المظلل هنا.' },

  // Dialogs
  dialog_upload_title: { en: 'Upload Documents', fr: 'Téléverser des documents', es: 'Subir Documentos', ar: 'رفع مستندات' },
  dialog_upload_drag: { en: 'Select or drag & drop files here', fr: 'Sélectionnez ou glissez-déposez des fichiers ici', es: 'Selecciona o arrastra archivos aquí', ar: 'حدد أو اسحب الملفات وأفلتها هنا' },
  dialog_upload_notice: {
    en: 'Documents are chunked and embedded locally into Qdrant vector database in the background.',
    fr: 'Les documents sont découpés et vectorisés localement dans Qdrant en arrière-plan.',
    es: 'Los documentos se fragmentan y se indexan localmente en Qdrant en segundo plano.',
    ar: 'يتم تقسيم المستندات وتضمينها محليًا في قاعدة بيانات Qdrant المتجهة في الخلفية.',
  },
  dialog_summary_title: { en: 'Generate Document Summary', fr: 'Générer un résumé', es: 'Generar Resumen', ar: 'تلخيص المستند' },
  dialog_summary_length: { en: 'Summary Length', fr: 'Longueur du résumé', es: 'Longitud del resumen', ar: 'طول الملخص' },
  dialog_summary_short: { en: 'Short (Key Takeaways)', fr: 'Court (Points clés)', es: 'Corto (Puntos clave)', ar: 'قصير (النقاط الأساسية)' },
  dialog_summary_medium: { en: 'Medium (Executive Overview)', fr: 'Moyen (Vue d\'ensemble)', es: 'Medio (Visión ejecutiva)', ar: 'متوسط (نظرة شاملة)' },
  dialog_summary_long: { en: 'Long (In-depth Synthesis)', fr: 'Long (Synthèse approfondie)', es: 'Largo (Síntesis profunda)', ar: 'شامل (تحليل مفصل)' },
  dialog_summary_pages: { en: 'Page Range (Optional, e.g. 1-5)', fr: 'Plage de pages (ex. 1-5)', es: 'Rango de páginas (ej. 1-5)', ar: 'نطاق الصفحات (اختياري، مثلاً 1-5)' },
  dialog_summary_generate: { en: 'Generate Summary', fr: 'Générer le résumé', es: 'Generar resumen', ar: 'توليد الملخص' },

  dialog_quiz_title: { en: 'Interactive Quiz Generator', fr: 'Générateur de quiz interactif', es: 'Generador de Cuestionarios', ar: 'منشئ الاختبارات التفاعلية' },
  dialog_quiz_count: { en: 'Number of Questions', fr: 'Nombre de questions', es: 'Número de preguntas', ar: 'عدد الأسئلة' },
  dialog_quiz_difficulty: { en: 'Difficulty', fr: 'Difficulté', es: 'Dificultad', ar: 'مستوى الصعوبة' },
  dialog_quiz_easy: { en: 'Easy', fr: 'Facile', es: 'Fácil', ar: 'سهل' },
  dialog_quiz_medium: { en: 'Medium', fr: 'Moyen', es: 'Medio', ar: 'متوسط' },
  dialog_quiz_hard: { en: 'Hard', fr: 'Difficile', es: 'Difícil', ar: 'صعب' },
  dialog_quiz_generate: { en: 'Create Quiz', fr: 'Créer le quiz', es: 'Crear cuestionario', ar: 'إنشاء الاختبار' },
  dialog_quiz_submit: { en: 'Submit Answers', fr: 'Valider mes réponses', es: 'Enviar respuestas', ar: 'تصحيح الإجابات' },
  dialog_quiz_score: { en: 'Your Score:', fr: 'Votre score :', es: 'Tu puntuación:', ar: 'نتيجتك:' },

  dialog_flashcards_title: { en: 'Study Flashcards', fr: 'Cartes mémo d\'étude', es: 'Tarjetas de Estudio', ar: 'بطاقات الاستذكار التعليمية' },
  dialog_flashcards_count: { en: 'Card Count', fr: 'Nombre de cartes', es: 'Número de tarjetas', ar: 'عدد البطاقات' },
  dialog_flashcards_flip: { en: 'Click card to flip', fr: 'Cliquez pour retourner', es: 'Clic para voltear', ar: 'انقر على البطاقة لقلبها' },
  dialog_flashcards_known: { en: 'I Know This', fr: 'Je maîtrise', es: 'Me lo sé', ar: 'أعرف هذه المعلومة' },
  dialog_flashcards_review: { en: 'Need Review', fr: 'À revoir', es: 'Necesito repasar', ar: 'تحتاج إلى مراجعة' },

  dialog_translate_title: { en: 'Document Translation', fr: 'Traduction de document', es: 'Traducción de Documento', ar: 'ترجمة المستند' },
  dialog_translate_source: { en: 'Source Language', fr: 'Langue source', es: 'Idioma de origen', ar: 'اللغة المصدر' },
  dialog_translate_target: { en: 'Target Language', fr: 'Langue cible', es: 'Idioma de destino', ar: 'اللغة الهدف' },
  dialog_translate_btn: { en: 'Translate', fr: 'Traduire', es: 'Traducir', ar: 'ترجمة' },

  // Landing / login page
  hero_meet: { en: 'Meet', fr: 'Découvrez', es: 'Conoce a', ar: 'تعرّف على' },
  hero_name: { en: 'LinguaDocs', fr: 'LinguaDocs', es: 'LinguaDocs', ar: 'لينغوادوكس' },
  hero_suffix: {
    en: ', your document AI.',
    fr: ', votre IA documentaire.',
    es: ', tu IA documental.',
    ar: '، ذكاؤك الوثائقي.',
  },
  hero_desc: {
    en: 'LinguaDocs reads through your PDFs, contracts, and research notes, answering questions with exact citations, generating quizzes, and summarizing content.',
    fr: 'LinguaDocs lit vos PDF, contrats et notes de recherche, répond avec des citations précises, génère des quiz et résume vos contenus.',
    es: 'LinguaDocs lee tus PDF, contratos y notas de investigación, responde con citas exactas, genera cuestionarios y resume contenido.',
    ar: 'يقرأ لينغوادوكس ملفات PDF والعقود وملاحظات البحث، ويجيب باقتباسات دقيقة، ويولّد اختبارات، ويلخص المحتوى.',
  },
  features_title: { en: 'Everything already built inside', fr: 'Tout est déjà intégré', es: 'Todo ya está integrado', ar: 'كل شيء مدمج بالفعل' },
  features_sub: {
    en: 'A full local RAG workspace — no cloud, no subscription.',
    fr: 'Un espace de travail RAG local complet — sans cloud, sans abonnement.',
    es: 'Un espacio de trabajo RAG local completo — sin la nube, sin suscripción.',
    ar: 'مساحة عمل RAG محلية كاملة — بدون سحابة واشتراك.',
  },
  feat_docs_title: { en: 'Upload & vectorize', fr: 'Téléversement & vectorisation', es: 'Subida y vectorización', ar: 'رفع وتحويل متجهي' },
  feat_docs_desc: {
    en: 'PDF, TXT, Markdown and DOCX up to 50MB, chunked and embedded into your local Qdrant database.',
    fr: 'PDF, TXT, Markdown et DOCX jusqu’à 50 Mo, découpés et vectorisés dans votre base Qdrant locale.',
    es: 'PDF, TXT, Markdown y DOCX de hasta 50MB, fragmentados e indexados en tu base Qdrant local.',
    ar: 'ملفات PDF وTXT وMarkdown وDOCX حتى 50 ميغابايت، مقسّمة ومدمجة في قاعدة Qdrant المحلية.',
  },
  feat_chat_title: { en: 'Grounded chat', fr: 'Chat ancré dans le document', es: 'Chat con evidencia', ar: 'محادثة موثقة' },
  feat_chat_desc: {
    en: 'Streaming answers with page-level citations, refusal banner when evidence is weak, stop button.',
    fr: 'Réponses en streaming avec citations par page, avertissement si les preuves sont faibles, bouton stop.',
    es: 'Respuestas en streaming con citas por página, aviso si la evidencia es débil, botón de parada.',
    ar: 'إجابات مباشرة باقتباسات على مستوى الصفحة، تنبيه عند ضعف الأدلة، وزر إيقاف.',
  },
  feat_viewer_title: { en: 'Document inspector', fr: 'Inspecteur de document', es: 'Inspector de documento', ar: 'معاين المستند' },
  feat_viewer_desc: {
    en: 'Click any citation to open the source page with the exact chunk highlighted.',
    fr: 'Cliquez sur une citation pour ouvrir la page source avec le segment exact surligné.',
    es: 'Haz clic en una cita para abrir la página de origen con el fragmento resaltado.',
    ar: 'انقر على أي استشهاد لفتح صفحة المصدر مع تمييز المقطع بدقة.',
  },
  feat_summary_title: { en: 'Summaries', fr: 'Résumés', es: 'Resúmenes', ar: 'الملخصات' },
  feat_summary_desc: {
    en: 'Short, medium or long synthesis of the whole document or a chosen page range.',
    fr: 'Synthèse courte, moyenne ou longue du document entier ou d’une plage de pages.',
    es: 'Síntesis corta, media o larga de todo el documento o de un rango de páginas.',
    ar: 'ملخص قصير أو متوسط أو طويل للمستند كاملاً أو لنطاق صفحات محدد.',
  },
  feat_quiz_title: { en: 'Interactive quiz', fr: 'Quiz interactif', es: 'Cuestionario interactivo', ar: 'اختبار تفاعلي' },
  feat_quiz_desc: {
    en: 'Multiple-choice questions generated from your document, with scoring and explanations.',
    fr: 'Questions à choix multiple générées depuis votre document, avec score et explications.',
    es: 'Preguntas de opción múltiple generadas desde tu documento, con puntuación y explicaciones.',
    ar: 'أسئلة اختيار من متعدد مولّدة من مستندك، مع نتيجة وشروحات.',
  },
  feat_flash_title: { en: 'Flashcards', fr: 'Cartes mémo', es: 'Tarjetas de estudio', ar: 'بطاقات الاستذكار' },
  feat_flash_desc: {
    en: 'Flip through study cards, track what you know and what needs review.',
    fr: 'Parcourez des cartes d’étude, suivez ce que vous maîtrisez et ce à revoir.',
    es: 'Repasa tarjetas, controla lo que sabes y lo que necesitas repasar.',
    ar: 'تصفح بطاقات المراجعة وتتبع ما تعرفه وما يحتاج إعادة.',
  },
  feat_translate_title: { en: 'Translation', fr: 'Traduction', es: 'Traducción', ar: 'الترجمة' },
  feat_translate_desc: {
    en: 'Translate documents between English, French, Spanish and Arabic side by side.',
    fr: 'Traduisez vos documents entre anglais, français, espagnol et arabe côte à côte.',
    es: 'Traduce documentos entre inglés, francés, español y árabe en paralelo.',
    ar: 'ترجم المستندات بين الإنجليزية والفرنسية والإسبانية والعربية جنبًا إلى جنب.',
  },
  feat_langs_title: { en: '4 languages, RTL', fr: '4 langues, RTL', es: '4 idiomas, RTL', ar: '4 لغات، من اليمين لليسار' },
  feat_langs_desc: {
    en: 'Full interface in EN / FR / ES / AR with right-to-left support for Arabic.',
    fr: 'Interface complète en EN / FR / ES / AR avec support droite-à-gauche pour l’arabe.',
    es: 'Interfaz completa en EN / FR / ES / AR con soporte de derecha a izquierda.',
    ar: 'واجهة كاملة بالإنجليزية والفرنسية والإسبانية والعربية مع دعم الاتجاه من اليمين لليسار.',
  },
  feat_local_title: { en: 'Local & private', fr: 'Local & privé', es: 'Local y privado', ar: 'محلي وخاص' },
  feat_local_desc: {
    en: 'Ollama LLM, BGE-m3 embeddings and Qdrant run on your machine. Your documents never leave.',
    fr: 'Le LLM Ollama, les embeddings BGE-m3 et Qdrant tournent sur votre machine. Vos documents restent chez vous.',
    es: 'El LLM de Ollama, los embeddings BGE-m3 y Qdrant funcionan en tu equipo. Tus documentos nunca salen.',
    ar: 'يعمل نموذج Ollama وBGE-m3 وQdrant على جهازك. لا تغادر مستنداتك جهازك أبدًا.',
  },

  code_inspector_title: { en: 'Streamlit Project Source Code', fr: 'Code source du projet Streamlit', es: 'Código fuente de Streamlit', ar: 'ملفات كود مشروع ستريمليت' },
  code_inspector_desc: {
    en: 'Inspect and copy the Python, CSS, and configuration files matching the redesign specifications.',
    fr: 'Consultez et copiez les fichiers Python, CSS et de configuration du projet.',
    es: 'Inspecciona y copia los archivos de Python, CSS y configuración de Streamlit.',
    ar: 'معاينة ونسخ ملفات بايثون وملفات التنسيق والإعدادات لمشروع ستريمليت المعاد تصميمه.',
  },
};

const t = (key, lang) => {
  const entry = translations[key];
  if (!entry) return key;
  return entry[lang] || entry['en'] || key;
};

/* Applique les textes/placeholder + dir RTL sur tous les [data-i18n] / [data-i18n-ph]. */
function applyI18n(lang) {
  document.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n, lang); });
  document.querySelectorAll('[data-i18n-ph]').forEach((el) => { el.placeholder = t(el.dataset.i18nPh, lang); });
  document.documentElement.lang = lang;
  document.documentElement.dir = isRTL(lang) ? 'rtl' : 'ltr';
}

window.LDI = { translations, t, isRTL, applyI18n };
