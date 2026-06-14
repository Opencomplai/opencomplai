import face_recognition


def identify_customer(image_bytes: bytes):
    return face_recognition.face_locations(image_bytes)
