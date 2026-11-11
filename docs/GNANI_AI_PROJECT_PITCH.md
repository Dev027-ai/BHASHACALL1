\# BHASHACALL

\## Speak in Your Language. Connect Without Language Barriers.



\*\*Built for:\*\* Gnani.ai Great Indian AI Internship Challenge  

\*\*Project Category:\*\* AI, Speech Technology \& Multilingual Communication



\---



\## 1. Project Overview



BhashaCall is an AI-powered multilingual voice-calling platform designed to help people communicate naturally even when they speak different languages.



Imagine a person speaking Hindi and another speaking English. Instead of typing messages into a translation app, both can communicate through a voice call. BhashaCall recognizes the speaker's speech, translates the message into the other participant's preferred language, and generates translated speech.



Powered by \*\*Gnani.ai Prisma v3.0 and Gnani.ai Timbre v2.5\*\*, BhashaCall aims to make multilingual communication more natural, accessible, and convenient.



\*\*Our vision:\*\* Language should connect people, not separate them.



\## 2. Problem Statement



India is home to extraordinary linguistic diversity. However, language differences can create communication barriers in everyday life.



People may struggle to communicate in situations involving:



\- \*\*Healthcare:\*\* Patients and caregivers who speak different languages.

\- \*\*Education:\*\* Students, teachers, and families from different linguistic backgrounds.

\- \*\*Travel:\*\* Visitors communicating with local communities.

\- \*\*Business:\*\* Customers and service providers discussing products and services.

\- \*\*Everyday communication:\*\* Friends, families, and individuals who are more comfortable speaking different languages.



Traditional translation applications often require users to type, translate, read, and play messages manually. This interrupts conversations and makes real-time communication inconvenient.



\*\*The core problem:\*\* People need a simpler way to speak naturally and understand someone who speaks another language.



\## 3. Proposed Solution



BhashaCall transforms multilingual communication into a voice-first experience.



It connects two participants through an internet-based voice room, where each participant independently selects:



\- Their speaking language.

\- Their preferred listening language.



The platform then processes their speech and delivers translated text and synthesized voice to the other participant.



\### Example



\- Person A speaks Hindi and wants to hear English.

\- Person B speaks English and wants to hear Hindi.

\- Person A speaks Hindi.

\- BhashaCall recognizes the speech, translates it into English, and generates English audio.

\- Person B receives the translated message.

\- When Person B responds in English, Person A receives Hindi translation and speech.



This creates a two-way multilingual conversation experience.



\## 4. How BhashaCall Works



The application follows a speech-to-translation-to-speech pipeline:



1\. \*\*Voice Capture:\*\* The browser captures the participant's microphone audio.

2\. \*\*Speech Recognition:\*\* Gnani.ai Prisma v3.0 converts spoken audio into text.

3\. \*\*Language Processing:\*\* The backend uses the participant's selected language direction.

4\. \*\*Translation:\*\* The translation layer converts the recognized text into the target language.

5\. \*\*Voice Generation:\*\* Gnani.ai Timbre v2.5 synthesizes translated speech.

6\. \*\*Delivery:\*\* The receiving participant gets translated captions and generated audio.



\*\*Core Pipeline:\*\*



`Speaker → Gnani Prisma → Translation Engine → Gnani Timbre → Listener`



\## 5. Gnani.ai Technology Integration



Gnani.ai is central to BhashaCall's speech experience.



\### Gnani Prisma v3.0 — Speech-to-Text



\- Converts spoken audio into text.

\- Supports the project's configured Indian-language locales.

\- Provides the recognized transcript for translation.

\- Forms the speech-recognition foundation of the calling workflow.



\### Gnani Timbre v2.5 — Text-to-Speech



\- Converts translated text into synthesized speech.

\- Enables listeners to hear messages in their preferred language.

\- Supports the project's configured voice catalogue.



\### Translation Engine



The backend connects recognized speech with the selected target language through a configurable translation integration.



Together, these technologies create a unified multilingual voice communication workflow.



\## 6. Innovation and Unique Features



BhashaCall focuses on making translation part of the conversation rather than a separate activity.



\*\*Key innovations:\*\*



\- \*\*Two-way multilingual communication:\*\* Both participants can speak in their own languages.

\- \*\*Independent language selection:\*\* Each participant controls their own speaking and listening language.

\- \*\*Voice-first interaction:\*\* Users communicate through speech instead of relying on typed translations.

\- \*\*AI-generated translated speech:\*\* Messages can be heard in the listener's selected language.

\- \*\*Live captions:\*\* Recognized and translated text helps participants follow conversations.

\- \*\*Indian-language focus:\*\* Designed around multilingual Indian communication and configured Indian-language speech models.

\- \*\*Integrated experience:\*\* Calling, speech recognition, translation, and voice generation work together in one application.



\## 7. Target Audience and Use Cases



| Audience | Potential Use Case |

|---|---|

| Travellers | Communicating with people who speak different languages |

| Patients and caregivers | Sharing basic needs across language barriers |

| Students | Communicating with educators from different linguistic backgrounds |

| Businesses | Supporting multilingual customer conversations |

| Families | Connecting relatives who prefer different languages |

| Communities | Making everyday conversations more accessible |



These are intended use cases. The platform is not a certified medical, legal, or emergency interpretation service.



\## 8. Expected Social Impact



BhashaCall aims to make digital communication more inclusive.



Its expected impact includes:



\- Reducing communication friction caused by language differences.

\- Making voice-based translation easier to access.

\- Helping people communicate without constantly switching between applications.

\- Supporting multilingual interaction across Indian communities.

\- Demonstrating practical applications of Indian speech AI.

\- Encouraging broader adoption of voice-first digital experiences.



The actual impact will be evaluated through user testing, translation-quality assessments, and real-world usability studies.



\## 9. Technology Stack



| Component | Technology |

|---|---|

| Speech-to-Text | Gnani.ai Prisma v3.0 |

| Text-to-Speech | Gnani.ai Timbre v2.5 |

| Backend | Python, FastAPI |

| Real-Time Communication | WebSockets, WebRTC |

| Frontend | React, TypeScript |

| Build Tool | Vite |

| Audio Processing | Web Audio API, PCM processing |

| Translation | Configurable translation service |

| Supporting Features | Captions, room management, chat translation, document processing |



\## 10. Supported Languages



The current project configuration includes:



| Language | Locale |

|---|---|

| Hindi | hi-IN |

| English (India) | en-IN |

| Bengali | bn-IN |

| Tamil | ta-IN |

| Telugu | te-IN |

| Marathi | mr-IN |



Language availability and translation quality depend on provider support, credentials, network conditions, and configuration. Testing with native speakers is essential.



\## 11. Challenges and Technical Approach



Building a multilingual voice communication experience involves several challenges:



\- Maintaining low latency during speech processing.

\- Handling different language directions for each participant.

\- Preserving meaning during translation.

\- Supporting Indian-language scripts and Unicode text correctly.

\- Managing audio streaming and playback.

\- Preventing incorrect language routing between participants.

\- Handling network interruptions and provider failures.



BhashaCall addresses these through participant-specific language settings, a backend-managed speech pipeline, Unicode-aware text handling, and modular translation-provider integration.



\## 12. Current Scope and Future Roadmap



\### Current MVP



\- Browser-based two-person voice rooms.

\- Independent participant language selection.

\- Gnani Prisma speech recognition integration.

\- Configurable translation pipeline.

\- Gnani Timbre speech synthesis integration.

\- Captions and supporting text-based features.



\### Future Roadmap



\- More continuous, low-latency streaming translation.

\- Improved handling of accents, dialects, and Hinglish.

\- Better background-noise handling.

\- Native Android and iOS applications.

\- Improved connection reliability and recovery.

\- More language coverage.

\- Privacy controls and clearer consent mechanisms.



\## 13. Responsible AI and Privacy



BhashaCall recognizes that communication can involve sensitive information.



The project aims to follow these principles:



\- Keep API credentials on the backend.

\- Avoid exposing provider secrets in frontend code.

\- Make AI processing clear to users.

\- Avoid presenting machine-generated translations as guaranteed or certified.

\- Encourage human verification for important medical, legal, financial, and emergency information.

\- Improve data handling and privacy controls as the platform develops.



\## 14. Demo Flow



A typical demonstration:



1\. Open BhashaCall in two browser sessions.

2\. Create a voice room in the first session.

3\. Join the same room from the second session.

4\. Select different speaking and listening languages.

5\. Start the voice call.

6\. Speak a short sentence in the first language.

7\. Demonstrate the recognized caption and translated output.

8\. Switch speakers and demonstrate the reverse translation.



This demonstrates how Gnani.ai speech technologies power the core multilingual communication experience.



\## 15. Short Project Pitch



\*\*BhashaCall is an AI-powered multilingual voice-calling platform that aims to remove language barriers from everyday conversations. It allows two people to speak naturally in their preferred languages while receiving translated text and synthesized speech. Using Gnani.ai Prisma v3.0 for speech recognition and Gnani.ai Timbre v2.5 for speech generation, alongside a configurable translation engine, BhashaCall brings speech recognition, translation, and voice synthesis together in one browser-based experience. Our mission is simple: make communication more accessible so that people can connect beyond language barriers.\*\*



\---



\*\*Project:\*\* BhashaCall  

\*\*Challenge:\*\* Gnani.ai Great Indian AI Internship Challenge  

\*\*Core AI Technologies:\*\* Gnani.ai Prisma v3.0 + Gnani.ai Timbre v2.5



\*BhashaCall is an internet-based calling MVP, not a translator for ordinary cellular/SIM calls. Features and language performance are subject to provider availability and ongoing testing.\*

