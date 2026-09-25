import cv2
from ultralytics import YOLO


def run_yolo26_color_webcam():
    # Load the latest lightweight YOLO26 model
    model = YOLO("yolo26n.pt")

    cam = "http://10.30.251.253:8080/video"
    cap = cv2.VideoCapture(cam)

    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    print("Running YOLO26 detection in full color. Press 'q' to exit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Run inference directly on the original full-color frame
        results = model(frame, stream=True)
        person_count = 0

        # Draw bounding boxes and class labels directly on the color image
        for r in results:
            person_count += sum(
                1
                for class_id in r.boxes.cls.tolist()
                if r.names[int(class_id)] == "person"
            )
            annotated_frame = r.plot()

        cv2.putText(
            annotated_frame,
            f"Persons: {person_count}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )
        cv2.imshow("YOLO26 Detection - Full Color", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run_yolo26_color_webcam()