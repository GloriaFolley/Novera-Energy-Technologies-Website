/* =========================================================
   NOVERA ENERGY & TECHNOLOGIES LTD
   MAIN JAVASCRIPT
========================================================= */


/* =========================================================
   CONFIGURATION
========================================================= */

const API_URL = "/api/consultation";


/* =========================================================
   SUPPORTED LANGUAGES
========================================================= */

const SUPPORTED_LANGUAGES = [
    "en",
    "fr",
    "de",
    "es",
    "tw",
    "ee",
    "da"
];

const LANGUAGE_NAMES = {
    en: "English",
    fr: "Français",
    de: "Deutsch",
    es: "Español",
    tw: "Twi",
    ee: "Ewe",
    da: "Dangme"
};

let currentLanguage =
    localStorage.getItem("noveraLanguage") || "en";

if (!SUPPORTED_LANGUAGES.includes(currentLanguage)) {
    currentLanguage = "en";
}


/* =========================================================
   DOM ELEMENTS
========================================================= */

const languageToggle =
    document.getElementById("languageToggle");

const languageMenu =
    document.getElementById("languageMenu");

const currentLanguageLabel =
    document.getElementById("currentLanguageLabel");

const consultationForm =
    document.getElementById("consultationForm");


/* =========================================================
   LANGUAGE DROPDOWN
========================================================= */

function initializeLanguageMenu() {

    if (!languageToggle || !languageMenu) {
        return;
    }

    languageToggle.addEventListener("click", function (event) {

        event.stopPropagation();

        const isOpen =
            languageMenu.classList.contains("show");

        languageMenu.classList.toggle("show");

        languageToggle.setAttribute(
            "aria-expanded",
            String(!isOpen)
        );
    });


    document
        .querySelectorAll(".language-menu button")
        .forEach(button => {

            button.addEventListener("click", function (event) {

                event.stopPropagation();

                setLanguage(
                    this.dataset.language
                );
            });
        });


    document.addEventListener("click", function () {

        closeLanguageMenu();

    });
}


function closeLanguageMenu() {

    if (languageMenu) {
        languageMenu.classList.remove("show");
    }

    if (languageToggle) {
        languageToggle.setAttribute(
            "aria-expanded",
            "false"
        );
    }
}


/* =========================================================
   CHANGE LANGUAGE
========================================================= */

function setLanguage(language) {

    if (!SUPPORTED_LANGUAGES.includes(language)) {
        language = "en";
    }

    currentLanguage = language;

    localStorage.setItem(
        "noveraLanguage",
        language
    );

    document.documentElement.lang = language;


    /* -----------------------------------------
       Translate normal elements
    ----------------------------------------- */

    document
        .querySelectorAll("[data-en]")
        .forEach(element => {

            const translation =
                element.getAttribute(
                    `data-${language}`
                );

            if (translation !== null) {
                element.innerHTML = translation;
            }
        });


    /* -----------------------------------------
       Translate placeholders
    ----------------------------------------- */

    document
        .querySelectorAll("[data-placeholder-en]")
        .forEach(element => {

            const placeholder =
                element.getAttribute(
                    `data-placeholder-${language}`
                );

            if (placeholder !== null) {
                element.placeholder = placeholder;
            }
        });


    /* -----------------------------------------
       Translate select options
    ----------------------------------------- */

    document
        .querySelectorAll("select option")
        .forEach(option => {

            const translation =
                option.getAttribute(
                    `data-${language}`
                );

            if (translation !== null) {
                option.textContent = translation;
            }
        });


    /* -----------------------------------------
       Selected language label
    ----------------------------------------- */

    if (currentLanguageLabel) {

        currentLanguageLabel.textContent =
            LANGUAGE_NAMES[language];

    }


    /* -----------------------------------------
       Active language button
    ----------------------------------------- */

    document
        .querySelectorAll(".language-menu button")
        .forEach(button => {

            button.classList.toggle(
                "active",
                button.dataset.language === language
            );

        });


    /* -----------------------------------------
       Hidden language form field
    ----------------------------------------- */

    const languageInput =
        document.getElementById("selectedLanguage");

    if (languageInput) {
        languageInput.value = language;
    }


    updateServiceButtons(language);

    closeLanguageMenu();
}


/* =========================================================
   SERVICE BUTTON TRANSLATIONS
========================================================= */

const serviceLabels = {

    en: {
        more: "Learn More",
        less: "Show Less"
    },

    fr: {
        more: "En savoir plus",
        less: "Réduire"
    },

    de: {
        more: "Mehr erfahren",
        less: "Weniger anzeigen"
    },

    es: {
        more: "Más información",
        less: "Mostrar menos"
    },

    tw: {
        more: "Kɔ so sua ho",
        less: "Fa no"
    },

    ee: {
        more: "Kpɔ nu geɖe",
        less: "Fa nu"
    },

    da: {
        more: "Kɔ nɔɔ nɛ",
        less: "Fa nɛ"
    }
};


function updateServiceButtons(language) {

    const labels =
        serviceLabels[language] ||
        serviceLabels.en;


    document
        .querySelectorAll(".service-card")
        .forEach(card => {

            const details =
                card.querySelector(".service-details");

            const button =
                card.querySelector(".service-link");

            if (!details || !button) {
                return;
            }

            button.textContent =
                details.classList.contains("show")
                    ? labels.less
                    : labels.more;
        });
}


/* =========================================================
   SERVICE DETAILS
========================================================= */

function toggleService(button) {

    const card =
        button.closest(".service-card");

    if (!card) {
        return;
    }

    const details =
        card.querySelector(".service-details");

    if (!details) {
        return;
    }


    const isCurrentlyOpen =
        details.classList.contains("show");


    /* Close all services */

    document
        .querySelectorAll(
            ".service-card .service-details"
        )
        .forEach(otherDetails => {

            otherDetails.classList.remove("show");

        });


    /* Open selected service */

    if (!isCurrentlyOpen) {
        details.classList.add("show");
    }


    updateServiceButtons(currentLanguage);
}


/* =========================================================
   HERO SLIDESHOW
========================================================= */

function initializeHeroSlideshow() {

    const slides =
        document.querySelectorAll(".hero-slide");

    const dots =
        document.querySelectorAll(".hero-dot");


    if (!slides.length) {
        return;
    }


    let currentSlide = 0;

    let timer;


    function showSlide(index) {

        slides.forEach((slide, i) => {

            slide.classList.toggle(
                "active",
                i === index
            );

        });


        dots.forEach((dot, i) => {

            dot.classList.toggle(
                "active",
                i === index
            );

        });


        currentSlide = index;
    }


    function nextSlide() {

        const next =
            (currentSlide + 1) %
            slides.length;

        showSlide(next);
    }


    function restartTimer() {

        clearInterval(timer);

        timer =
            setInterval(
                nextSlide,
                5000
            );
    }


    dots.forEach(dot => {

        dot.addEventListener(
            "click",
            function () {

                const index =
                    Number(this.dataset.slide);

                if (
                    index >= 0 &&
                    index < slides.length
                ) {

                    showSlide(index);

                    restartTimer();
                }
            }
        );
    });


    showSlide(0);

    restartTimer();
}


/* =========================================================
   ACTIVE NAVIGATION
========================================================= */

function initializeNavigation() {

    const sections =
        document.querySelectorAll("section[id]");

    const links =
        document.querySelectorAll("nav a[href^='#']");


    if (!sections.length || !links.length) {
        return;
    }


    function updateNavigation() {

        let currentSection = "";

        const scrollPosition =
            window.scrollY + 180;


        sections.forEach(section => {

            if (
                scrollPosition >=
                section.offsetTop
            ) {

                currentSection =
                    section.id;
            }
        });


        links.forEach(link => {

            link.classList.toggle(
                "active",
                link.getAttribute("href") ===
                `#${currentSection}`
            );

        });
    }


    window.addEventListener(
        "scroll",
        updateNavigation,
        { passive: true }
    );


    updateNavigation();
}


/* =========================================================
   SMOOTH SCROLL
========================================================= */

function initializeSmoothScroll() {

    document
        .querySelectorAll('a[href^="#"]')
        .forEach(link => {

            link.addEventListener(
                "click",
                function (event) {

                    const targetID =
                        this.getAttribute("href");

                    if (
                        !targetID ||
                        targetID === "#"
                    ) {
                        return;
                    }


                    const target =
                        document.querySelector(
                            targetID
                        );


                    if (!target) {
                        return;
                    }


                    event.preventDefault();


                    target.scrollIntoView({
                        behavior: "smooth",
                        block: "start"
                    });
                }
            );
        });
}


/* =========================================================
   FORM MESSAGES
========================================================= */

const formMessages = {

    en: {
        sending: "Sending...",
        success:
            "Thank you. Your consultation request has been received.",
        error:
            "We could not process your request. Please try again.",
        connection:
            "Could not connect to the Novera server.",
        nameRequired:
            "Please enter your name.",
        phoneRequired:
            "Please enter your phone number.",
        serviceRequired:
            "Please select a service."
    },


    fr: {
        sending: "Envoi...",
        success:
            "Merci. Votre demande de consultation a été reçue.",
        error:
            "Nous n'avons pas pu traiter votre demande.",
        connection:
            "Impossible de se connecter au serveur Novera.",
        nameRequired:
            "Veuillez entrer votre nom.",
        phoneRequired:
            "Veuillez entrer votre numéro de téléphone.",
        serviceRequired:
            "Veuillez sélectionner un service."
    },


    de: {
        sending: "Wird gesendet...",
        success:
            "Vielen Dank. Ihre Beratungsanfrage wurde erhalten.",
        error:
            "Ihre Anfrage konnte nicht verarbeitet werden.",
        connection:
            "Verbindung zum Novera-Server konnte nicht hergestellt werden.",
        nameRequired:
            "Bitte geben Sie Ihren Namen ein.",
        phoneRequired:
            "Bitte geben Sie Ihre Telefonnummer ein.",
        serviceRequired:
            "Bitte wählen Sie eine Dienstleistung."
    },


    es: {
        sending: "Enviando...",
        success:
            "Gracias. Hemos recibido su solicitud de consulta.",
        error:
            "No pudimos procesar su solicitud.",
        connection:
            "No se pudo conectar con el servidor de Novera.",
        nameRequired:
            "Introduzca su nombre.",
        phoneRequired:
            "Introduzca su número de teléfono.",
        serviceRequired:
            "Seleccione un servicio."
    },


    tw: {
        sending: "Rekɔ...",
        success:
            "Yɛda wo ase. Yɛagye wo consultation request no.",
        error:
            "Yɛantumi anyɛ wo request no.",
        connection:
            "Yɛantumi anka Novera server no ho.",
        nameRequired:
            "Yɛsrɛ wo, kyerɛ wo din.",
        phoneRequired:
            "Yɛsrɛ wo, kyerɛ wo phone number.",
        serviceRequired:
            "Yɛsrɛ wo, paw service bi."
    },


    ee: {
        sending: "Ele ɖom...",
        success:
            "Akpe. Míxɔ wò biabia la.",
        error:
            "Míete ŋu wɔ wò biabia la.",
        connection:
            "Míete ŋu kplɔ Novera server la gbɔ.",
        nameRequired:
            "Taflatse ŋlɔ wò ŋkɔ.",
        phoneRequired:
            "Taflatse ŋlɔ wò telefon nɔmba.",
        serviceRequired:
            "Taflatse tia dɔwɔnu aɖe."
    },


    da: {
        sending: "Eja...",
        success:
            "Oyiwaladɔŋ. Yɛagye wo nɔŋɔ request no.",
        error:
            "Yɛantumi anyɛ wo request no.",
        connection:
            "Yɛantumi anka Novera server no ho.",
        nameRequired:
            "Yɛsrɛ wo, kyerɛ wo din.",
        phoneRequired:
            "Yɛsrɛ wo, kyerɛ wo phone number.",
        serviceRequired:
            "Yɛsrɛ wo, paw service bi."
    }
};


function getFormMessage(language, type) {

    const messages =
        formMessages[language] ||
        formMessages.en;

    return (
        messages[type] ||
        formMessages.en[type]
    );
}


/* =========================================================
   FORM STATUS
========================================================= */

function showFormStatus(message, type) {

    const status =
        document.getElementById("formStatus");

    if (!status) {
        return;
    }

    status.textContent = message;

    status.className =
        `form-status show ${type}`;
}


function clearFormStatus() {

    const status =
        document.getElementById("formStatus");

    if (!status) {
        return;
    }

    status.textContent = "";

    status.className =
        "form-status";
}


/* =========================================================
   CONSULTATION FORM
========================================================= */

function initializeConsultationForm() {

    if (!consultationForm) {
        return;
    }


    consultationForm.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();


            const submitButton =
                consultationForm.querySelector(
                    "button[type='submit']"
                );


            const formData =
                new FormData(consultationForm);


            const name =
                String(
                    formData.get("name") || ""
                ).trim();


            const email =
                String(
                    formData.get("email") || ""
                ).trim();


            const phone =
                String(
                    formData.get("phone") || ""
                ).trim();


            const service =
                String(
                    formData.get("service") || ""
                ).trim();


            const message =
                String(
                    formData.get("message") || ""
                ).trim();


            /* -----------------------------------------
               VALIDATION
            ----------------------------------------- */

            if (!name) {

                showFormStatus(
                    getFormMessage(
                        currentLanguage,
                        "nameRequired"
                    ),
                    "error"
                );

                return;
            }


            if (!phone) {

                showFormStatus(
                    getFormMessage(
                        currentLanguage,
                        "phoneRequired"
                    ),
                    "error"
                );

                return;
            }


            if (!service) {

                showFormStatus(
                    getFormMessage(
                        currentLanguage,
                        "serviceRequired"
                    ),
                    "error"
                );

                return;
            }


            /* -----------------------------------------
               DISABLE BUTTON
            ----------------------------------------- */

            if (submitButton) {

                submitButton.disabled = true;

                submitButton.textContent =
                    getFormMessage(
                        currentLanguage,
                        "sending"
                    );
            }


            clearFormStatus();


            try {

                /* -----------------------------------------
                   SEND TO FLASK
                ----------------------------------------- */

                const response =
                    await fetch(
                        API_URL,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({
                                name,
                                email,
                                phone,
                                service,
                                message,
                                language:
                                    currentLanguage
                            })
                        }
                    );


                const result =
                    await response
                        .json()
                        .catch(() => ({}));


                if (
                    !response.ok ||
                    !result.success
                ) {

                    throw new Error(
                        result.message ||
                        getFormMessage(
                            currentLanguage,
                            "error"
                        )
                    );
                }


                /* -----------------------------------------
                   SUCCESS
                ----------------------------------------- */

                showFormStatus(
                    getFormMessage(
                        currentLanguage,
                        "success"
                    ),
                    "success"
                );


                consultationForm.reset();


                /* Restore language */

                const languageInput =
                    document.getElementById(
                        "selectedLanguage"
                    );

                if (languageInput) {

                    languageInput.value =
                        currentLanguage;
                }


            } catch (error) {

                console.error(
                    "Novera consultation error:",
                    error
                );


                showFormStatus(
                    getFormMessage(
                        currentLanguage,
                        "connection"
                    ),
                    "error"
                );


            } finally {

                if (submitButton) {

                    submitButton.disabled = false;


                    const translatedLabel =
                        submitButton.getAttribute(
                            `data-${currentLanguage}`
                        );


                    submitButton.textContent =
                        translatedLabel ||
                        "Request Consultation";
                }
            }
        }
    );
}


/* =========================================================
   START APPLICATION
========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        initializeLanguageMenu();

        initializeHeroSlideshow();

        initializeNavigation();

        initializeSmoothScroll();

        initializeConsultationForm();

        setLanguage(currentLanguage);

    }
);
