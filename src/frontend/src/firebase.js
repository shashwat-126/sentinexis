import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyB8DK0qXqWL2rHWqkp9v0RjucdgyonAMm0",
  authDomain: "sentinexis.firebaseapp.com",
  projectId: "sentinexis",
  storageBucket: "sentinexis.firebasestorage.app",
  messagingSenderId: "491021589942",
  appId: "1:491021589942:web:7e0c5b784ed004e9327517",
};

const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);
export default app;
