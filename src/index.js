// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  apiKey: "AIzaSyCmVX6RYZViKY_Pt8ZojID2uI2fyT9pw34",
  authDomain: "friendlyfoes.firebaseapp.com",
  databaseURL: "https://friendlyfoes-default-rtdb.firebaseio.com",
  projectId: "friendlyfoes",
  storageBucket: "friendlyfoes.firebasestorage.app",
  messagingSenderId: "496353965686",
  appId: "1:496353965686:web:3b8e92e63411eea85ed157",
  measurementId: "G-9BLTV0B25M"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);