import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
import xml.etree.ElementTree as ET
from lib.map import HeatMap
from sklearn.metrics import jaccard_similarity_score
import scipy

class GC_executor:
    def __init__(self):
        pass

    def _display_image(self, image):
        # plt.axis('off')
        frame = plt.gca()
        frame.axes.get_xaxis().set_ticks([])
        frame.axes.get_yaxis().set_ticks([])
        plt.imshow(image)
        plt.show()

    def grab_cut_with_patch(self, patch, heat_map):
        # Grabcut mask
        # DRAW_BG = {'color': BLACK, 'val': 0}
        # DRAW_FG = {'color': WHITE, 'val': 1}
        # DRAW_PR_FG = {'color': GREEN, 'val': 3}
        # DRAW_PR_BG = {'color': RED, 'val': 2}

        self.bgdModel = np.zeros((1, 65), np.float64)
        self.fgdModel = np.zeros((1, 65), np.float64)

        mean = np.mean(heat_map[heat_map != 0])
        heat_map_high_prob = np.where((heat_map > mean), 1, 0).astype('uint8')
        heat_map_low_prob = np.where((heat_map > 0), 3, 0).astype('uint8')
        mask = heat_map_high_prob + heat_map_low_prob
        mask[mask == 4] = 1
        mask[mask == 0] = 2

        mask, bgdModel, fgdModel = cv2.grabCut(patch, mask, None, self.bgdModel, self.fgdModel, 5, cv2.GC_INIT_WITH_MASK)

        mask = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
        img = patch * mask[:, :, np.newaxis]
        return img

    def grab_cut_without_patch(self, patch):
        bgdModel = np.zeros((1, 65), np.float64)
        fgdModel = np.zeros((1, 65), np.float64)

        mask_onlyGC = np.zeros(patch.shape[:2], np.uint8)
        rect = (0, 0, patch.shape[1] - 1, patch.shape[0] - 1)

        cv2.grabCut(patch, mask_onlyGC, rect, bgdModel, fgdModel, 10, cv2.GC_INIT_WITH_RECT)

        mask_onlyGC = np.where((mask_onlyGC == 2) | (mask_onlyGC == 0), 0, 1).astype('uint8')
        img = patch * mask_onlyGC[:, :, np.newaxis]
        return img

class Enhancer:
    def __init__(self, path_to_images, path_to_annotations, path_to_enhanced_annotations, actual_segmentation_annotation_path, img_file_extension='jpg'):

        self.heatmap_obj = HeatMap()

        self.img_path = path_to_images
        self.annotation_path = path_to_annotations
        self.dest_annotation_path = path_to_enhanced_annotations
        self.img_file_extension = img_file_extension
        self.actual_segmentation_annotation_path = actual_segmentation_annotation_path
        self._validate_paths()

    def _validate_paths(self):
        # Can check whether the number of files in the annotations is the same as the number of images
        pass

    def _assert_path(self, path, error_message):
        assert os.path.exists(path), error_message

    def _display_image(self, image):
        # plt.axis('off')
        frame = plt.gca()
        frame.axes.get_xaxis().set_ticks([])
        frame.axes.get_yaxis().set_ticks([])
        plt.imshow(image)
        plt.show()

    def _display_images(self, images):
        plt.figure(figsize=(20, 10))
        columns = 5
        for i, image in enumerate(images):
            plt.subplot(len(images) / columns + 1, columns, i + 1)
            frame = plt.gca()
            frame.axes.get_xaxis().set_ticks([])
            frame.axes.get_yaxis().set_ticks([])
            plt.imshow(image)
        plt.show()

    def _save_images(self, images, name):
        plt.figure(figsize=(20, 10))
        columns = 5
        for i, image in enumerate(images):
            plt.subplot(len(images) / columns + 1, columns, i + 1)
            frame = plt.gca()
            frame.axes.get_xaxis().set_ticks([])
            frame.axes.get_yaxis().set_ticks([])
            plt.imshow(image)
        plt.savefig(name, bbox_inches='tight')

    def enhance(self, file_name, only_gc=True):
        gc = GC_executor()

        # Read the corresponding image
        image_path = os.path.join(self.img_path, file_name + '.' + self.img_file_extension)
        self._assert_path(image_path, 'The image file for annotation is not found at: ' + image_path)

        image = cv2.imread(image_path, cv2.IMREAD_COLOR)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        segmented_image = np.zeros_like(image)
        combined_heat_map = np.zeros((image.shape[:2]))

        # Parse the xml annotation
        annotation_xml = open(os.path.join(self.annotation_path, file_name + '.xml'), 'r')
        tree = ET.parse(annotation_xml)
        root = tree.getroot()

        # For each bb-annotation in annotation:
        patches = []
        heatmaps = []
        gc_results = []
        for i, annotation in enumerate(root.findall('./object')):
            xmin = int(annotation.find('./bndbox/xmin').text)
            ymin = int(annotation.find('./bndbox/ymin').text)
            xmax = int(annotation.find('./bndbox/xmax').text)
            ymax = int(annotation.find('./bndbox/ymax').text)

            # Crop the patch
            patch = image[ymin:ymax, xmin:xmax]
            patches.append(patch)

            # Get the objectness
            heat_map = self.heatmap_obj.get_map(patch)
            heat_map = heat_map.data * ~heat_map.mask
            objectness_heatmap = cv2.applyColorMap(np.uint8(-heat_map), cv2.COLORMAP_JET)
            heatmaps.append(heat_map)
            combined_heat_map[ymin:ymax, xmin:xmax] = heat_map

        # Save the image
        img = gc.grab_cut_with_patch(np.copy(image), np.copy(combined_heat_map))
        img_gc_only = gc.grab_cut_without_patch(np.copy(image))

        gc_results.append(image)
        # gc_results.append(cv2.applyColorMap(np.uint8(-combined_heat_map), cv2.COLORMAP_JET))
        gc_results.append(combined_heat_map)
        gc_results.append(img)
        gc_results.append(img_gc_only)
        annotation_image = cv2.imread(os.path.join(self.actual_segmentation_annotation_path, file_name + '.png'), cv2.IMREAD_COLOR)
        gc_results.append(annotation_image)

        # Visualize the output
        # self._display_images(patches)
        # self._display_images(heatmaps)
        # self._display_images(gc_without_objectness)
        self._display_images(gc_results)
        # self._save_images(gc_results, os.path.join(self.dest_annotation_path, file_name+'.png'))
        # self._display_image(combined_heat_map)

    '''
    Generated outputs using supervised and unsupervised methods.
    '''
    def enhance_combined(self, file_name, only_gc=True):
        gc = GC_executor()

        # Read the corresponding image
        image_path = os.path.join(self.img_path, file_name + '.' + self.img_file_extension)
        self._assert_path(image_path, 'The image file for annotation is not found at: ' + image_path)

        image = cv2.imread(image_path, cv2.IMREAD_COLOR)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        combined_heat_map = np.zeros((image.shape[:2]))

        # Parse the xml annotation
        annotation_xml = open(os.path.join(self.annotation_path, file_name + '.xml'), 'r')
        tree = ET.parse(annotation_xml)
        root = tree.getroot()

        # For each bb-annotation in annotation:
        patches = []
        heatmaps = []
        gc_results = []
        ground_truth_boxes = np.zeros((image.shape[:2]))
        for i, annotation in enumerate(root.findall('./object')):
            xmin = int(annotation.find('./bndbox/xmin').text)
            ymin = int(annotation.find('./bndbox/ymin').text)
            xmax = int(annotation.find('./bndbox/xmax').text)
            ymax = int(annotation.find('./bndbox/ymax').text)

            # Crop the patch
            patch = image[ymin:ymax, xmin:xmax]
            patches.append(patch)

            # Get the objectness
            heat_map = self.heatmap_obj.get_map(patch)
            heat_map = heat_map.data * ~heat_map.mask
            objectness_heatmap = cv2.applyColorMap(np.uint8(-heat_map), cv2.COLORMAP_JET)
            heatmaps.append(heat_map)
            combined_heat_map[ymin:ymax, xmin:xmax] = heat_map
            ground_truth_boxes [ymin:ymax, xmin:xmax] = np.ones_like(heat_map)

        # GrabCut
        img = gc.grab_cut_with_patch(np.copy(image), np.copy(combined_heat_map))
        img_gc_only = gc.grab_cut_without_patch(np.copy(image))

        #
        # # Unsupervised
        heat_map = self.heatmap_obj.get_map(image)
        heat_map_unsupervised = heat_map.data * ~heat_map.mask
        img_unsupervised = gc.grab_cut_with_patch(np.copy(image), np.copy(heat_map_unsupervised))

        gc_results.append(image)
        # gc_results.append(heat_map_unsupervised)
        gc_results.append(cv2.cvtColor(cv2.applyColorMap(np.uint8(heat_map_unsupervised), cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB))
        gc_results.append(img_unsupervised)
        # gc_results.append(cv2.cvtColor(cv2.applyColorMap(np.uint8(combined_heat_map), cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB))
        # # gc_results.append(combined_heat_map)
        # gc_results.append(img)
        gc_results.append(img_gc_only)
        annotation_image = cv2.imread(os.path.join(self.actual_segmentation_annotation_path, file_name + '.png'), cv2.IMREAD_COLOR)
        gc_results.append(annotation_image)

        # self._display_image(combined_heat_map)
        # self._display_image(ground_truth_boxes)
        self._display_images(gc_results)
        # self._save_images(gc_results, os.path.join(self.dest_annotation_path, file_name+'.png'))

if __name__ == '__main__':
    np.set_printoptions(threshold='nan')

    img_db_path = os.path.join('/home/joseph/Dataset/voc_2012/VOCdevkit/VOC2012/JPEGImages/')
    annotation_path = os.path.join('/home/joseph/Dataset/voc_2012/VOCdevkit/VOC2012/Annotations/')
    dest_annotation_path = os.path.join('/home/joseph/paper_results_unsupervised/bad_examples')
    actual_segmentation_annotation_path = os.path.join('/home/joseph/Dataset/voc_2012/VOCdevkit/VOC2012/SegmentationClass/')

    e = Enhancer(img_db_path, annotation_path, dest_annotation_path, actual_segmentation_annotation_path)

    # total_length = len(os.listdir(actual_segmentation_annotation_path))
    # for i, annotation_file in enumerate(os.listdir(actual_segmentation_annotation_path)):
    #     if os.path.isfile(os.path.join(actual_segmentation_annotation_path, annotation_file)):
    #         image = annotation_file.split('.')[0]
    #         print 'Processing ', image, ' (', i, ' of ', total_length, ')'
    #         e.enhance(image)

    image_names = ["2007_000042", "2007_000363", "2007_000676",
                   "2007_000799", "2007_001073", "2007_001239",
                   "2007_001397", "2007_001416", "2007_002088",
                   "2007_003910", "2007_004143", "2007_004856",
                   "2007_005130", "2007_008051", "2007_009082",
                   "2008_002835", "2008_002904", "2008_003379",
                   "2008_007239", "2009_000664", "2009_005137",
                   "2010_001995"]

    image_names = ["2007_002488", "2007_002823", "2007_003876",
                   "2007_005304", "2007_006647", "2008_001208",
                   "2009_002425"]


    for i, image in enumerate(image_names):
        e.enhance_combined(image)
        print 'Processing ', image, 'i: ', i

    print('Done.')
