from flask import Blueprint, request, jsonify, send_file
from app.database import db, fs
from bson import ObjectId
from io import BytesIO
from pymongo import errors

images_bp = Blueprint('images', __name__)

 
@images_bp.route('/upload', methods=['POST'])
def upload_image():
    # Check for required fields in the request
    if 'images' not in request.files or 'title' not in request.form or 'level' not in request.form:
        return jsonify({'error': 'Missing required fields in the request'}), 400
    
    level = request.form['level']
    category = request.form["category"]
    title = request.form['title']
    live = request.form['live']
    live_link = request.form.get('live_link', '')  # Default to an empty string if not provided
    date_time = request.form['date_time']
    
    # Get puzzle number from the request or default to 1 if not provided
    puzzle_number = request.form.get('puzzle_number', '1')
    
    files = request.files.getlist('images')
    if not files:
        return jsonify({'error': 'No files uploaded'}), 400

    file_ids_dict = {}
    try:
        for i, file in enumerate(files):
            file_id = fs.put(file, filename=file.filename, content_type=file.content_type)
            puzzle_key = f'puzzle{puzzle_number}'  # Use puzzle_number to create the key
            file_ids_dict[puzzle_key] = {
                'id': str(file_id),
                'move': "Black to Move",
                'solution': None,  # Placeholder, update as needed
                'sid_link': None  # Placeholder, update as needed
            }
    except Exception as e:
        return jsonify({'error': f'Failed to upload file: {str(e)}'}), 500

    try:
        existing_image_set = db.image_sets.find_one({
            'title': title,
            'level': level,
            'category': category,
            'live': live,
            'live_link': live_link,
            'date_time': date_time
        })

        if existing_image_set:
            print("Existing image set found, updating...")
            print(f"Existing file_ids: {existing_image_set.get('file_ids', {})}")
            updated_file_ids = existing_image_set.get('file_ids', {})
            updated_file_ids.update(file_ids_dict)
            print(f"Updated file_ids: {updated_file_ids}")
            
            update_result = db.image_sets.update_one(
                {'title': title, 'level': level, 'category': category, 'live': live, 'date_time': date_time},
                {'$set': {'file_ids': updated_file_ids}}
            )
            print(f"Update Result: {update_result.modified_count} document(s) modified.")
        else:
            print("No existing image set found, inserting new record...")
            db.image_sets.insert_one({
                'level': level,
                'title': title,
                'category': category,
                'live': live,
                'live_link': live_link,
                'date_time': date_time,
                'file_ids': file_ids_dict
            })
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

    return jsonify({'message': 'Images uploaded successfully', 'file_ids': file_ids_dict}), 200

@images_bp.route('/updatelivepuzzle', methods=['POST'])
def update_live_puzzle():
    # Extract parameters from the request
    data = request.get_json()
    level = data.get('level')
    category = data.get('category')
    title = data.get('title')
    live = data.get('live')
    live_link = data.get('live_link')

    # Validate required parameters
    if not (level and category and title):
        return jsonify({'error': 'Missing required parameters'}), 400

    # Construct the query
    query = {
        'level': level,
        'category': category,
        'title': title
    }

    # Construct the update dictionary dynamically
    update = {}
    if live is not None:
        update['live'] = live
    if live_link is not None:
        update['live_link'] = live_link

    # Check if there's anything to update
    if not update:
        return jsonify({'error': 'No update parameters provided'}), 400

    # Prepare the update operation
    update_operation = {'$set': update}

    try:
        # Update the document in the database
        result = db.image_sets.update_one(query, update_operation)

        # Handle the result of the update operation
        if result.matched_count == 0:
            return jsonify({'error': 'No matching document found'}), 404
        if result.modified_count == 0:
            return jsonify({'error': 'Document not updated'}), 500

        return jsonify({
            'message': 'Document updated successfully',
            'updated_fields': update
        }), 200

    except Exception as e:
        return jsonify({'error': f'Error updating puzzle data: {str(e)}'}), 500

@images_bp.route('/getpuzzleid', methods=['GET'])
def get_puzzle():
    level = request.args.get('level')
    category = request.args.get('category')
    title = request.args.get('title')
    live = request.args.get('live')
    puzzle_number = request.args.get('puzzle_number')

    if not (level and category and title and live and puzzle_number):
        return jsonify({'error': 'Missing required parameters'}), 400

    # Construct the query to find the image set
    query = {
        'level': level,
        'category': category,
        'title': title,
        'live': live
    }

    try:
        image_set = db.image_sets.find_one(query)
        if not image_set:
            return jsonify({'error': 'Image set not found'}), 404
        
        # Extract the file_ids and puzzle info
        puzzle_info = image_set.get('file_ids', {}).get(f'puzzle{puzzle_number}', {})
        
        response = {
            'level': image_set.get('level'),
            'category': image_set.get('category'),
            'title': image_set.get('title'),
            'live': image_set.get('live'),
            'date_time': image_set.get('date_time'),
            'live_link':image_set.get('live_link',''),
            'file_ids': {
                f'puzzle{puzzle_number}':{
                'id': puzzle_info.get('id'),
                'move': puzzle_info.get('move',''),
                'solution': puzzle_info.get('solution',''),
                'sid_link': puzzle_info.get('sid_link','')
                }
            }
        }
        return jsonify(response), 200

    except Exception as e:
        return jsonify({'error': f'Error retrieving puzzle data: {str(e)}'}), 500


@images_bp.route('/get_puzzle_sol', methods=['PUT'])
def update_puzzle_sol():
    # Extract data from request
    data = request.json
    level = data.get('level')
    category = data.get('category')
    title = data.get('title')
    live = data.get('live')
    live_link = data.get('live_link','')  # New field
    column_name = data.get('column_name')
    move = data.get('move','')
    sid_link = data.get('sid_link','')
    solution = data.get('solution','')

    if not all([level, category, title, live, column_name]):
        return jsonify({'error': 'Missing required fields in the request'}), 400

    # Build the update query
    update_query = {
        '$set': {
            f'file_ids.{column_name}.move': move,
            f'file_ids.{column_name}.sid_link': sid_link,
            f'file_ids.{column_name}.solution': solution,
            'live_link': live_link  # Add or update the live_link field
        }
    }

    # Find and update the document
    try:
        result = db.image_sets.update_one(
            {
                'title': title,
                'level': level,
                'category': category,
                'live': live,
            },
            update_query
        )
        
        if result.matched_count == 0:
            return jsonify({'error': 'No matching document found'}), 404
        
        return jsonify({'message': 'Puzzle updated successfully'}), 200

    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
 


@images_bp.route('/images/title', methods=['GET'])
def get_images_by_title():
    title=request.args.get('title')
    level = request.args.get('level')
    category = request.args.get('category')
    try:
        # Find the image set by both title and level
        image_set = db.image_sets.find_one({'title': title, 'level': level,'category': category})
        if not image_set:
            return jsonify({'error': 'No images found with the given title and level'}), 404
        print(image_set)

        image_data = []
        for file_id in image_set['file_ids']:
            file = fs.get(ObjectId(image_set['file_ids'][file_id]['id']))
            image_data.append({
                'id': image_set['file_ids'][file_id]['id'],
                'filename': file.filename,
                'url': f"/image/{image_set['file_ids'][file_id]['id']}"
            })

        return jsonify({'images': image_data}), 200
    except errors.PyMongoError as e:
        return jsonify({'error': str(e)}), 500

@images_bp.route('/imagesets', methods=['GET'])
def get_image_sets():
    try:
        # Fetch all records from the image_sets collection, sorted by _id in descending order
        image_sets = list(db.image_sets.find({}).sort('_id', -1))
        
        # Convert ObjectId to string and return all fields
        for image_set in image_sets:
            image_set['_id'] = str(image_set['_id'])  # Convert ObjectId to string
        
        return jsonify(image_sets), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@images_bp.route('/images/solutions', methods=['GET'])
def get_images_by_solutions():
    title = request.args.get('title')
    level = request.args.get('level')
    category = request.args.get('category')
    search_id = request.args.get('id')
    
    try:
        # Find the image set by title, level, and category
        image_set = db.image_sets.find_one({
            'title': title,
            'level': level,
            'category': category
        })
        
        if not image_set:
            return jsonify({'error': 'No images found with the given title, level, and category'}), 404

        image_data = []

        # Check if 'id' is provided and find the corresponding image
        if search_id:
            for puzzle_key, puzzle_value in image_set.get('file_ids', {}).items():
                if puzzle_value['id'] == search_id:
                    image_data.append(puzzle_value)
                    break

        return jsonify({'images': image_data}), 200

    except errors.PyMongoError as e:
        return jsonify({'error': str(e)}), 500


@images_bp.route('/get_level', methods=['GET'])
def get_level_images():
    level = request.args.get('level')  # Get the level parameter from the query string
    if not level:
        return jsonify({'error': 'Level parameter is required'}), 400

    try:
        # Query to find image sets that match the specified level
        image_sets = db.image_sets.find({'level': level}).sort('_id', -1)
        
        sets_data = []
        for image_set in image_sets:
            sets_data.append({
                        'level': image_set.get('level', ''),
                        'live': image_set.get('live', ''),
                        'title': image_set.get('title', ''),
                        'category': image_set.get('category', ''),
                        'live_link': image_set.get('live_link', ''),  # Use get() to handle optional field
                        'date_time': image_set.get('date_time', ''),
                        'file_ids': image_set.get('file_ids', {})
            })
        
        if not sets_data:
            return jsonify({'message': 'No image sets found for this level'}), 404

        return jsonify({'image_sets': sets_data}), 200
    except errors.PyMongoError as e:
        return jsonify({'error': str(e)}), 500
    
@images_bp.route('/image_get_fileid', methods=['POST'])
def image_fileid_get():
    try:
        data = request.get_json()
        file_id = data['file_id']
        
        file = fs.get(ObjectId(file_id))
        return send_file(BytesIO(file.read()), mimetype=file.content_type, as_attachment=False, download_name=file.filename)
    except errors.PyMongoError as e:
        return jsonify({'error': str(e)}), 500
    except KeyError:
        return jsonify({'error': 'File ID is required'}), 400


@images_bp.route('/delete-arena-title', methods=['DELETE'])
def delete_images():
    try:
        data = request.json
        title = data.get('title')
        level = data.get('level')
        category = data.get('category')
        
         

        print('Received data:', {'title': title, 'level': level,'category':category})  # Log received data

        if not title or not level:
            return jsonify({'error': 'Title and level are required'}), 400

        # Find the image set to be deleted
        image_set = db.image_sets.find_one({'title': title, 'level': level,'category':category})
        print("imm",image_set)
        if not image_set:
            return jsonify({'error': 'No image set found with the specified title'}), 404

        file_ids = image_set.get('file_ids', [])

        # Loop over each file_id and delete related records from fs.files and fs.chunks
        for file_id_obj in file_ids:
            try:
                print("hi",file_ids[file_id_obj])
                print(file_ids[file_id_obj]["id"])
                 # file_id_obj = file_id
                
                # Delete the file document from fs.files
                fs_files_delete_result = db.fs.files.delete_one({'_id': ObjectId(file_ids[file_id_obj]["id"])})
                
                if fs_files_delete_result.deleted_count == 0:
                    return jsonify({'error': f'File with id {file_id_obj} not found in fs.files'}), 404
 
                # Delete the related chunks from fs.chunks
                fs_chunks_delete_result = db.fs.chunks.delete_many({'files_id': ObjectId(file_ids[file_id_obj]["id"])})

            except errors.PyMongoError as e:
                return jsonify({'error': f'Error deleting file or chunks with id  : {str(e)}'}), 500

        # Delete the entire image set document
        delete_result = db.image_sets.delete_one({'title': title, 'level': level,'category':category})
        if delete_result.deleted_count == 0:
            return jsonify({'error': 'Failed to delete the image set document'}), 500

        return jsonify({'message': f'Files, chunks, and image set related to title "{title}" have been deleted successfully.'}), 200

    except errors.PyMongoError as e:
        return jsonify({'error': str(e)}), 500

    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500


