# photo_organizer.py

import os
import sys
import hashlib
import shutil
from PIL import Image
from PIL.ExifTags import TAGS
import datetime

# --- PART 1: Scan Files and Identify Photos ---
def get_image_files(folders):
    """
    Scans the given list of folders recursively to find image files.
    Returns a list of absolute paths to the image files.
    """
    print("\n--- Étape: Scan des fichiers ---")
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
    image_files = []
    for folder in folders:
        # Note: Basic folder validation is now done before calling this function
        # (in the main function's input handling)
        print(f"Scan du dossier: {folder}")
        try:
            for root, _, files in os.walk(folder):
                for file in files:
                    # Get file extension and make it lowercase for case-insensitive comparison
                    file_extension = os.path.splitext(file)[1].lower()
                    if file_extension in image_extensions:
                        image_files.append(os.path.join(root, file))
        except Exception as e:
             print(f"Erreur lors du scan du dossier {folder}: {e}")

    print(f"Trouvé {len(image_files)} fichiers image au total.")
    return image_files

# --- PART 2: Duplicate Detection ---
def calculate_hash(filepath, blocksize=65536):
    """Calculates the MD5 hash of a file."""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            buf = f.read(blocksize)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(blocksize)
        return hasher.hexdigest()
    except (IOError, OSError) as e:
        # print(f"Erreur lors du calcul du hash pour {filepath}: {e}") # Too verbose
        return None # Return None for unreadable files

def find_duplicates(image_paths):
    """
    Finds duplicate files based on size and then MD5 hash.
    Returns a dictionary where keys are hashes and values are lists of file paths.
    Groups with more than one path are duplicates.
    """
    print("\n--- Étape: Recherche de doublons ---")
    # First, group by size (optimization)
    files_by_size = {}
    for filepath in image_paths:
        try:
            # Check if file exists and is accessible before getting size
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                if file_size not in files_by_size:
                    files_by_size[file_size] = []
                files_by_size[file_size].append(filepath)
            else:
                 print(f"Attention: Fichier introuvable ou inaccessible, ignoré: {filepath}")
        except (IOError, OSError) as e:
             print(f"Erreur lors de la lecture de la taille de {filepath}: {e}")
             # Skip this file

    # Now, group by hash for files with the same size
    duplicates = {}
    processed_files = 0
    total_files_to_hash = sum(len(l) for l in files_by_size.values() if len(l) > 1) # Only hash groups > 1 file

    print(f"Vérification du contenu pour les groupes de taille identique ({total_files_to_hash} fichiers potentiellement à hacher)...")

    for size, file_list in files_by_size.items():
        if len(file_list) > 1: # Only process groups with more than one file of the same size
            files_by_hash = {}
            for filepath in file_list:
                file_hash = calculate_hash(filepath)
                processed_files += 1
                # Optional: print progress
                # if processed_files % 100 == 0:
                #      print(f"Progression hash: {processed_files}/{total_files_to_hash}", end='\r')

                if file_hash: # Only if hash was calculated successfully
                    if file_hash not in files_by_hash:
                        files_by_hash[file_hash] = []
                    files_by_hash[file_hash].append(filepath)

            # Any hash with more than one file path is a duplicate group
            for file_hash, paths in files_by_hash.items():
                if len(paths) > 1:
                    duplicates[file_hash] = paths # Store the group of duplicates
    # print("\n") # New line after progress print
    print(f"Recherche de doublons terminée. Trouvé {len(duplicates)} groupes de doublons.")
    return duplicates

# --- PART 3: Duplicate Handling ---
def handle_duplicates(duplicate_groups, action="list", target_folder="duplicates"):
    """
    Handles the identified duplicate groups.
    action: "list", "move", or "delete" (use "delete" with extreme caution!)
    target_folder: Folder to move duplicates to (if action is "move").
    """
    if not duplicate_groups:
        print("Aucun doublon trouvé.")
        return

    print("\n--- Gestion des doublons ---")

    if action == "move":
        if not os.path.exists(target_folder):
            try:
                os.makedirs(target_folder)
                print(f"Création du dossier de destination pour les doublons: {target_folder}")
            except OSError as e:
                print(f"Erreur: Impossible de créer le dossier pour les doublons {target_folder}: {e}")
                print("Action de déplacement annulée.")
                action = "list" # Fallback to list if folder creation fails

    processed_groups = 0
    moved_count = 0
    deleted_count = 0

    for hash_val, paths in duplicate_groups.items():
        processed_groups += 1
        print(f"\nGroupe de doublons {processed_groups}/{len(duplicate_groups)} (hash: {hash_val[:8]}...):")

        # Decide which one to keep (e.g., the one with the earliest creation date, or just the first one found)
        # For simplicity, we keep the first one in the list provided by find_duplicates.
        original = paths[0]
        duplicates_to_process = paths[1:] # All others are potential duplicates

        print(f"  Original (gardé): {original}")

        if not duplicates_to_process:
            print("  (Ce groupe n'a qu'un seul fichier, devrait être ignoré si l'algorithme fonctionne correctement)")
            continue

        print("  Doublons trouvés:")
        for dup_path in duplicates_to_process:
            print(f"    - {dup_path}")

        if action == "list":
            pass # Already listed above
        elif action == "move":
            print("  Action: Déplacement des doublons...")
            for dup_path in duplicates_to_process:
                # Check if file still exists before moving (might have been moved/deleted by a previous run)
                if not os.path.exists(dup_path):
                     print(f"    Attention: Le doublon {dup_path} n'existe plus, ignoré.")
                     continue
                try:
                    # Construct new path in the target folder
                    # Keep original filename. Add counter if needed.
                    dup_filename = os.path.basename(dup_path)
                    new_path = os.path.join(target_folder, dup_filename)

                    # Handle potential name collisions in target folder
                    base, ext = os.path.splitext(new_path)
                    counter = 1
                    while os.path.exists(new_path):
                         new_path = f"{base}_{counter}{ext}"
                         counter += 1

                    shutil.move(dup_path, new_path)
                    print(f"    Déplacé: {dup_path} -> {new_path}")
                    moved_count += 1
                except (IOError, OSError) as e:
                    print(f"    Erreur lors du déplacement de {dup_path}: {e}")
        elif action == "delete":
             print("  Action: Suppression des doublons...")
             # !!! DANGEROUS !!! ADD USER CONFIRMATION HERE BEFORE DELETING!
             confirm = input(f"  Confirmez la suppression de {len(duplicates_to_process)} doublons listés ci-dessus [O/N] ? ").lower()
             if confirm == 'o':
                 for dup_path in duplicates_to_process:
                     # Check if file still exists before deleting
                     if not os.path.exists(dup_path):
                          print(f"    Attention: Le doublon {dup_path} n'existe plus, ignoré pour la suppression.")
                          continue
                     try:
                         os.remove(dup_path)
                         print(f"    Supprimé: {dup_path}")
                         deleted_count += 1
                     except (IOError, OSError) as e:
                         print(f"    Erreur lors de la suppression de {dup_path}: {e}")
             else:
                 print("  Suppression annulée pour ce groupe.")
        else:
            print(f"  Action '{action}' non reconnue. Aucune action effectuée pour ce groupe.")

    print("\n--- Gestion des doublons terminée ---")
    if action == "move":
        print(f"Total de fichiers doublons déplacés: {moved_count}")
    elif action == "delete":
        print(f"Total de fichiers doublons supprimés: {deleted_count}")


# --- PART 4: Photo Sorting ---
def get_photo_date(filepath):
    """
    Attempts to get the date from EXIF data (DateTimeOriginal or DateTimeDigitized).
    Falls back to file modification date if EXIF is not available or unreadable.
    Returns a datetime object or None if date cannot be determined.
    """
    try:
        # Open image and read EXIF data
        image = Image.open(filepath)
        exif_data = {}
        if hasattr(image, '_getexif'):
            info = image._getexif()
            if info:
                for tag, value in info.items():
                    decoded = TAGS.get(tag, tag)
                    exif_data[decoded] = value

        image.close() # Close the image file handle immediately

        # Prioritize DateTimeOriginal or DateTimeDigitized from EXIF
        date_str = exif_data.get('DateTimeOriginal') or exif_data.get('DateTimeDigitized')

        if date_str:
            try:
                # EXIF date format is typically 'YYYY:MM:DD HH:MM:SS'
                # Some software might write it differently, robust parsing could be needed for production
                return datetime.datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
            except ValueError:
                # print(f"Attention: Format de date EXIF inattendu pour {filepath}: {date_str} - Fallback to mtime.")
                pass # Fallback to modification date below if EXIF format is wrong
    except Exception as e: # Catch potential errors opening image or reading EXIF
        # print(f"Impossible de lire EXIF pour {filepath}: {e} - Fallback to mtime.")
        pass # Silently fail EXIF read, fallback to mtime

    # Fallback to modification date if EXIF failed or was not present
    try:
        timestamp = os.path.getmtime(filepath)
        return datetime.datetime.fromtimestamp(timestamp)
    except Exception as e:
        print(f"Erreur lors de la lecture de la date de modification pour {filepath}: {e}")
        return None

def sort_photos(image_paths, destination_base_folder):
    """
    Sorts photos into a date-based folder structure.
    Example structure: destination_base_folder/YYYY/MM/DD/filename.ext
    Uses get_photo_date to determine the date.
    """
    print("\n--- Étape: Tri des photos ---")

    if not image_paths:
        print("Aucune photo à trier.")
        return

    if not os.path.exists(destination_base_folder):
        try:
            os.makedirs(destination_base_folder)
            print(f"Création du dossier de destination pour le tri: {destination_base_folder}")
        except OSError as e:
            print(f"Erreur: Impossible de créer le dossier pour le tri {destination_base_folder}: {e}")
            print("Tri annulé.")
            return

    processed_count = 0
    skipped_count = 0

    for filepath in image_paths:
        # Check if file still exists before trying to sort (e.g., if it was moved as a duplicate)
        if not os.path.exists(filepath):
            # print(f"Attention: Fichier introuvable ou déjà déplacé, ignoré pour le tri: {filepath}")
            skipped_count += 1
            continue

        photo_date = get_photo_date(filepath)

        if photo_date:
            # Create destination path like destination_base_folder/YYYY/MM/DD/
            year_folder = os.path.join(destination_base_folder, str(photo_date.year))
            month_folder = os.path.join(year_folder, photo_date.strftime('%m')) # MM format
            day_folder = os.path.join(month_folder, photo_date.strftime('%d')) # DD format

            # Ensure destination folder exists
            try:
                os.makedirs(day_folder, exist_ok=True)
            except OSError as e:
                 print(f"Erreur: Impossible de créer le dossier de destination {day_folder} pour {filepath}: {e}. Fichier ignoré pour le tri.")
                 skipped_count += 1
                 continue # Skip this file

            # Construct new file path
            filename = os.path.basename(filepath)
            new_filepath = os.path.join(day_folder, filename)

            # Handle potential filename collisions in destination
            # This handles cases where photos with the same name from different sources end up in the same date folder
            base, ext = os.path.splitext(new_filepath)
            counter = 1
            original_new_filepath = new_filepath
            while os.path.exists(new_filepath):
                # Check if the file at new_filepath is actually the SAME file as the source file
                # This prevents renaming if the file is already where it should be
                try:
                    if os.path.samefile(filepath, new_filepath):
                        # print(f"Fichier déjà à sa place: {filepath}")
                        break # File is already sorted correctly, no need to move or rename
                except FileNotFoundError:
                    # One of the files might not exist anymore, continue with rename logic
                    pass # os.path.exists check at loop start will handle if new_filepath is invalid

                new_filepath = f"{base}_{counter}{ext}"
                counter += 1

            # Only move if the destination path is different from the original path
            try:
                 if os.path.abspath(filepath) == os.path.abspath(new_filepath) and os.path.exists(new_filepath):
                      # File is already in the correct location with the correct name
                      # print(f"Fichier déjà à sa place: {filepath}")
                      pass
                 else:
                    shutil.move(filepath, new_filepath)
                    # print(f"Déplacé: {filepath} -> {new_filepath}")
                    processed_count += 1
            except (IOError, OSError) as e:
                print(f"Erreur lors du déplacement de {filepath} vers {new_filepath}: {e}. Fichier ignoré.")
                skipped_count += 1
        else:
            # print(f"Impossible de déterminer la date pour {filepath}. Ignoré pour le tri.") # Too verbose
            skipped_count += 1


    print(f"Tri terminé. {processed_count} fichiers déplacés/triés.")
    if skipped_count > 0:
        print(f"{skipped_count} fichiers ignorés (date non déterminable, erreur, ou déjà traités).")


# --- Main Function ---
def main():
    """
    Main function to orchestrate the photo organization process.
    Handles input (command line args or interactive), finds duplicates,
    handles duplicates based on user choice, and sorts photos.
    """
    print("--- Application de Tri et Nettoyage de Photos ---")

    folders_to_process = []

    # --- Handle Input Folders (Command Line or Interactive) ---
    if len(sys.argv) > 1:
        # Option 1: Get folders from command line arguments
        folders_from_args = sys.argv[1:]
        print(f"Lecture des dossiers depuis les arguments de la ligne de commande.")
        # Simple validation for command line arguments
        valid_folders = [f for f in folders_from_args if os.path.isdir(f)]
        invalid_folders = [f for f in folders_from_args if not os.path.isdir(f)]
        if invalid_folders:
             print(f"Attention: Les chemins suivants ne sont pas des dossiers valides et seront ignorés: {invalid_folders}")
        folders_to_process = valid_folders

    else:
        # Option 2: Prompt user for input if no arguments provided
        print("\nAucun dossier spécifié en argument.")
        print("Veuillez entrer le(s) chemin(s) complet(s) des dossiers à scanner.")
        print("Séparez les chemins par des virgules (par exemple: C:/Users/Moi/PhotosVacances, /home/moi/Pictures/Famille).")
        folder_input = input("Entrez le(s) chemin(s): ")

        # Split input string by commas, remove leading/trailing whitespace, filter out empty strings
        input_paths = [f.strip() for f in folder_input.split(',') if f.strip()]

        # Validate input paths are actual directories
        valid_folders = [f for f in input_paths if os.path.isdir(f)]
        invalid_folders = [f for f in input_paths if not os.path.isdir(f)]

        if invalid_folders:
            print(f"Attention: Les chemins suivants ne sont pas des dossiers valides et seront ignorés: {invalid_folders}")

        folders_to_process = valid_folders

    # --- Check if any valid folders were provided ---
    if not folders_to_process:
        print("\nAucun dossier valide à traiter fourni. Le programme va s'arrêter.")
        return # Exit the script if no valid folders

    print(f"\nDossier(s) valide(s) à traiter: {folders_to_process}")

    # --- Step 2: Scan files ---
    all_image_paths = get_image_files(folders_to_process)

    if not all_image_paths:
        print("\nAucun fichier image trouvé dans les dossiers spécifiés. Le programme va s'arrêter.")
        return # Exit if no images found

    # --- Step 3: Find duplicates ---
    duplicate_groups = find_duplicates(all_image_paths)

    # --- Step 4: Handle duplicates ---
    if duplicate_groups:
        print("\n--- Que voulez-vous faire des doublons trouvés ? ---")
        print("  l: Lister uniquement les groupes de doublons (action par défaut)")
        print("  m: Déplacer les doublons (gardant un original) vers un sous-dossier 'doublons_trouves'")
        print("  d: Supprimer les doublons (gardant un original) - ATTENTION, CETTE ACTION EST DÉFINITIVE ET DANGEREUSE !")

        duplicate_action_choice = input("Entrez votre choix (l, m, d): ").lower()

        duplicate_action = "list" # Default action
        if duplicate_action_choice == 'm':
            duplicate_action = "move"
            duplicates_output_folder = os.path.join(os.getcwd(), "doublons_trouves") # Create in current working directory
            handle_duplicates(duplicate_groups, action=duplicate_action, target_folder=duplicates_output_folder)
        elif duplicate_action_choice == 'd':
            duplicate_action = "delete"
             # handle_duplicates function already includes a confirmation prompt for delete
            handle_duplicates(duplicate_groups, action=duplicate_action)
        else:
            print("Choix non valide ou 'l'. Liste des doublons affichée ci-dessus.")
            handle_duplicates(duplicate_groups, action="list") # Ensure listing is shown clearly

    else:
        print("\nAucun doublon trouvé. Pas de gestion de doublons nécessaire.")

    # --- Step 5: Sort photos ---
    # Important: If duplicates were moved/deleted, some paths in all_image_paths might not exist anymore.
    # The sort_photos function is designed to check os.path.exists before processing each file,
    # so we can pass the original list.
    print("\n--- Voulez-vous trier les photos restantes par date ? ---")
    print("  o: Oui, trier les photos (crée une structure Année/Mois/Jour)")
    print("  n: Non, ignorer le tri (action par défaut)")
    sort_confirm = input("Entrez votre choix (o, n): ").lower()

    if sort_confirm == 'o':
        destination_sort_folder = os.path.join(os.getcwd(), "photos_triees_par_date") # Create in current working directory
        print(f"Les photos seront triées dans: {destination_sort_folder}")
        sort_photos(all_image_paths, destination_sort_folder)
    else:
        print("Tri des photos ignoré.")

    print("\n--- Traitement terminé ---")

# --- Entry Point ---
if __name__ == "__main__":
    # IMPORTANT: Running the script directly will execute the main() function.
    # If running via VS Code's "Run Python File" button, it also runs main().
    # To pass command line arguments in VS Code:
    # 1. Go to Run -> Add Configuration...
    # 2. Select "Python File".
    # 3. This creates a launch.json file in a .vscode folder.
    # 4. Find the configuration for your script (it might be named "Python: Current File").
    # 5. Add an "args" list with your folder paths:
    #    "args": ["/chemin/vers/dossier1", "/chemin/vers/dossier2"]
    # 6. Save launch.json.
    # 7. Now, when you run using the "Run and Debug" sidebar (Ctrl+Shift+D) and select this configuration,
    #    it will pass the arguments.
    # If you run from the integrated terminal using `python photo_organizer.py ...`, arguments work directly.

    # --- WARNING ---
    # Always test on copies of your photos first!
    # The 'delete' option is dangerous.
    # By default, the move/sort destination folders are created in the current working directory.
    # Ensure you know where that is or modify the script to ask for destination folders.

    main()