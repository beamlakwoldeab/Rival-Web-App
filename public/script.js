
import { getAuth, } from "firebase/auth";
import { getFirestore, doc, setDoc, serverTimestamp } from "firebase/firestore"; // Import Firestore functions
import { firebaseConfig } from "./firebase-config.js";

// Initialize firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app); // Initialize Firestore

  







