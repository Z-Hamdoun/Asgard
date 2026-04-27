#include <stdlib.h>
#include <stdbool.h>

typedef struct {
    float x_min, x_max, y_min, y_max;
    int id;
} BBox;

typedef struct {
    int id1, id2, id3;
} Result;

// Vérifie si a est inclus dans b
bool is_contained(BBox a, BBox b) {
    return (a.x_min >= b.x_min && a.x_max <= b.x_max &&
            a.y_min >= b.y_min && a.y_max <= b.y_max);
}

// Fonction principale
int find_nested_triplets(BBox* boxes, int n, Result* results, int max_res) {
    int count = 0;
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            if (i == j || !is_contained(boxes[i], boxes[j])) continue;
            
            for (int k = 0; k < n; k++) {
                if (j == k || i == k || !is_contained(boxes[j], boxes[k])) continue;
                
                // On a trouvé : i inclus dans j, lui-même inclus dans k
                if (count < max_res) {
                    results[count++] = (Result){boxes[i].id, boxes[j].id, boxes[k].id};
                }
            }
        }
    }
    return count;
}