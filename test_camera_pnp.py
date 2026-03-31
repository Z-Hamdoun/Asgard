#!/usr/bin/env python3
"""
Script de test pour la détection PnP avec la webcam du PC.
Affiche les points détectés et le vecteur de positionnement en temps réel.
"""

import cv2
import sys
import os
import numpy as np

# Ajoute le chemin vers le module algo.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pnp'))

from algo import PnPLandingSystem

def draw_detected_points(frame, pnp_system):
    """
    Détecte et affiche UNIQUEMENT les 5 points magenta sélectionnés sur la frame.
    Retourne aussi les points 2D détectés pour visualisation.
    """
    # Traitement Image (même que dans algo.py)
    blurred = cv2.GaussianBlur(frame, (5, 5), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, pnp_system.lower_hsv1, pnp_system.upper_hsv1) + \
           cv2.inRange(hsv, pnp_system.lower_hsv2, pnp_system.upper_hsv2)
    
    opening = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3,3), np.uint8), iterations=pnp_system.iterations)
    closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, np.ones((3,3), np.uint8), iterations=pnp_system.iterations)
    
    contours, _ = cv2.findContours(closing, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    valid_contours = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        ratio = w/h
        if cv2.contourArea(c) > pnp_system.min_contour_area and ratio > pnp_system.min_circularity_ratio:
            valid_contours.append(c)
    
    # Prend les 5 plus grands contours (sélection finale)
    valid_contours = sorted(valid_contours, key=cv2.contourArea, reverse=True)[:5]
    
    # Extrait les centres des 5 points sélectionnés UNIQUEMENT
    points_2d = []
    for i, c in enumerate(valid_contours):
        M = cv2.moments(c)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
            points_2d.append([cX, cY])
            
            # Dessine un cercle pour chaque point sélectionné
            cv2.circle(frame, (cX, cY), 8, (0, 255, 255), -1)  # Cyan rempli
            cv2.circle(frame, (cX, cY), 10, (0, 255, 255), 2)   # Contour cyan
            
            # Affiche le numéro du point
            cv2.putText(frame, str(i+1), (cX+15, cY-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    
    return points_2d

def main():
    # Initialise le système PnP (laptop=True pour utiliser les paramètres de la webcam PC)
    pnp_system = PnPLandingSystem(marker_distance=0.40, net_depth=0.20)
    
    # Ouvre la webcam (0 = caméra par défaut)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ Erreur : Impossible d'ouvrir la webcam")
        return
    
    print("✅ Webcam ouverte")
    print("\n📋 Instructions:")
    print("  - Placez des points magenta (rose) devant la caméra")
    print("  - Appuyez sur 'q' pour quitter")
    print("  - Appuyez sur 's' pour prendre une capture d'écran")
    print("  - Appuyez sur 'v' pour activer/désactiver le mode verbose\n")
    
    verbose = True
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("❌ Erreur : Impossible de lire la frame")
            break
        
        # Redimensionne pour voir mieux (optionnel)
        frame = cv2.resize(frame, (1280, 720))
        
        frame_count += 1
        
        # Détecte et affiche les points magenta
        detected_points = draw_detected_points(frame, pnp_system)
        
        # Exécute la détection PnP
        result = pnp_system.get_landing_vector(frame, verbose=verbose)
        
        # Prépare le texte à afficher
        if result is not None:
            dx, dy, dz = result
            status_text = f"✅ Détecté | dx={dx:.3f}m | dy={dy:.3f}m | dz={dz:.3f}m"
            color = (0, 255, 0)  # Vert
        else:
            status_text = "❌ Non détecté (besoin de 5 points magenta)"
            color = (0, 0, 255)  # Rouge
        
        # Affiche le texte sur la frame
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.putText(frame, f"Frame: {frame_count} | Verbose: {'ON' if verbose else 'OFF'} | Points: {len(detected_points)}/5", 
                   (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Affiche la frame
        cv2.imshow('PnP Landing System Test', frame)
        
        # Gestion des touches clavier
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("\n👋 Sortie...")
            break
        elif key == ord('s'):
            filename = f"pnp_test_{frame_count}.png"
            cv2.imwrite(filename, frame)
            print(f"📸 Screenshot sauvé: {filename}")
        elif key == ord('v'):
            verbose = not verbose
            print(f"🔊 Mode verbose: {'ACTIVÉ' if verbose else 'DÉSACTIVÉ'}")
    
    # Libère les ressources
    cap.release()
    cv2.destroyAllWindows()
    print("✅ Programme terminé")

if __name__ == "__main__":
    main()
