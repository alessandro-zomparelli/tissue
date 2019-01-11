# Tissue
![cover](http://www.co-de-it.com/wordpress/wp-content/uploads/2015/07/tissue_graphics.jpg)
Tissue - Blender's add-on for computational design by Co-de-iT
http://www.co-de-it.com/wordpress/code/blender-tissue

### Blender 2.79

Official version (master): https://github.com/alessandro-zomparelli/tissue/archive/master.zip

Latest development version (dev1): https://github.com/alessandro-zomparelli/tissue/tree/dev1
(Includes animatable Tessellation)

### Blender 2.80

Latest development version (b280-dev): https://github.com/alessandro-zomparelli/tissue/tree/b280-dev
(Includes animatable Tessellation and Patch method)



### Installation:

1. Start Blender. Open User Preferences, the addons tab 
2. Click "install from file" and point Blender at the downloaded zip
3. Activate Tissue add-on from user preferences
3. Save user preferences if you want to have it on at startup.


### Contribute
Please help me keeping Tissue stable and updated, report any issue here: https://github.com/alessandro-zomparelli/tissue/issues

Tissue is free and open-source. I really think that this is the power of Blender and I wanted to give my small contribution to it.
If you like my work and you want to help to continue the development of Tissue, please consider to make a small donation. Any small contribution is really appreciated, thanks! :-D

Alessandro


[![paypal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=ARSDJWXVFZ346)

## Tissue Tools

![image](http://alessandrozomparelli.com/tissue/Tissue%20Tools.jpg)

## Tissue Tools - Weight Paint

![image](http://alessandrozomparelli.com/tissue/Tissue%20Tools%20-%20Weight%20Paint.jpg)

### Weight Generate

#### Area
Weight from Faces area (Automatic Bounds, Manual Bounds)

![image](http://alessandrozomparelli.com/tissue/Weight%20-%20Area.jpg)

#### Curvature
Weight from Curvature (Based on *Dirty Vertex Colors*)

![image](http://alessandrozomparelli.com/tissue/Weight%20-%20Curvature.jpg)

#### Weight Formula
Weight based on Vertices parameters.
Allows to use vertices coordinates and normals direction. Integer and Float sliders can be created in order to find the proper parameters more easily.

![image](http://alessandrozomparelli.com/tissue/Weight%20-%20Formula.jpg)

#### Harmonic
Harmonic function based on active Weight

![image](http://alessandrozomparelli.com/tissue/Weight%20-%20Harmonic.jpg)

#### Convert to Colors
Convert active Weight to Vertex Colors

![image](http://alessandrozomparelli.com/tissue/Weight%20-%20Colors.jpg)

### Deformation Analysis

#### Edges Deformation
Generate a Vertex Group based on Edges Deformation evaluated on the Modifiers result (Deformation Modifiers and Simulations)

![image](http://alessandrozomparelli.com/tissue/Weight%20-%20Edges%20Deformation.jpg)

#### Edges Bending
Generate a Vertex Group based on Edges Bending evaluated on the Modifiers result (Deformation Modifiers and Simulations)

![image](http://alessandrozomparelli.com/tissue/Weight%20-%20Edges%20Bending.jpg)

### Weight Contour

#### Contour Curves
Generates isocurves based on Avtive Weight.

![image](http://alessandrozomparelli.com/tissue/Contour%20-%20Curves.jpg)

#### Contour Displace
Cut the mesh according to active Weight in a variable number of isocurves and automatically add a Displace Modifier.

![image](http://alessandrozomparelli.com/tissue/Contour%20-%20Displace.jpg)

#### Contour Mask
Trim the mesh according to active Weight. 

![image](http://alessandrozomparelli.com/tissue/Contour%20-%20Mask.jpg)

### Simulations

#### Reaction Diffusion
*Work in Progress* 


## Tissue Tools - Vertex Paint

![image](http://alessandrozomparelli.com/tissue/Tissue%20Tools%20-%20Verte%20Paint.jpg)

#### Convert to Weight
Convert Vertex Color to Vertex Group (Red Channel, Green Channel, Blue Channel, Value Channel, Invert)

![image](http://alessandrozomparelli.com/tissue/Convert%20to%20Weight.jpg)
