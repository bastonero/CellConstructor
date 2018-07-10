#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Wed Jun  6 10:29:32 2018

@author: pione
"""
import Structure
import numpy as np
import os
import scipy, scipy.optimize
import matplotlib.pyplot as plt

import Methods

BOHR_TO_ANGSTROM = 0.52918

class Phonons:
    """
    Phonons
    ================
    
    
    This class contains the phonon of a given structure.
    It can be used to show and display dinamical matrices, as well as for operating 
    with them
    """
    def __init__(self, structure = None, nqirr = 1, full_name = False):
        """
        INITIALIZE PHONONS
        ==================
        
        The dynamical matrix for a given structure.
        
        Parameters
        ----------
            - structure : type(Structure)  or  type(string)
                This is the atomic structure for which you want to use the phonon calculation.
                It is needed to correctly initialize all the arrays.
                It can be both the Structure, or a filepath containing a quantum ESPRESSO
                dynamical matrix. Up to now only ibrav0 dymat are supported.
            - nqirr : type(int) , default 1
                The number of irreducible q point of the supercell on which you want 
                to compute the phonons. 
                Use 1 if you want to perform a Gamma point calculation.
            - full_name : bool
                If full_name is True, then the structure is loaded without appending the
                q point index. This is compatible only with nqirr = 1.
                
        Results
        -------
            - Phonons : this
                It returns the Phonon class initializated.
        """
        
        # Initialize standard variables
        self.dynmats = []
        self.nqirr = nqirr
        # Q tot contains the total q points (also those belonging to the same star)
        self.q_tot = []
        
        # Prepare additional information that can be loaded
        self.dielectric_tensor = None
        self.effective_charges = None
        self.raman_tensor = None
        
        # This alat is read just from QE, but not used
        self.alat = 1
        
        # If this is true then the dynmat can be used
        self.initialized = False
        
        # This contains all the q points in the stars of the irreducible q point
        self.q_stars = []
        self.structure = None
        
        # Check whether the structure argument is a path or a Structure
        if (type(structure) == type("hello there!")):
            # Quantum espresso
            self.LoadFromQE(structure, nqirr, full_name = full_name)
        elif (type(structure) == type(Structure.Structure())):   
            # Get the structure
            self.structure = structure
            
            if structure.N_atoms <= 0:
                raise ValueError("Error, the given structure cannot be empty.")
            
            # Check that nqirr has a valid value
            if nqirr <= 0:
                raise ValueError("Error, nqirr argument must be a strictly positive number.")
            
            self.dynmats = []
            for i in nqirr:
                # Create a dynamical matrix
                self.dynmats.append(np.zeros((3 * structure.N_atoms, 3*structure.N_atoms)))
        
                
    def LoadFromQE(self, fildyn_prefix, nqirr=1, full_name = False):
        """
        This Function loads the phonons information from the quantum espresso dynamical matrix.
        the fildyn prefix is the prefix of the QE dynamical matrix, that must be followed by numbers from 1 to nqirr.
        All the dynamical matrices are loaded.
        
        
        Parameters
        ----------
            - fildyn_prefix : type(string)
                Quantum ESPRESSO dynmat prefix (the files are followed by the q irreducible index)
            - nqirr : type(int), default 1
                Number of irreducible q points in the space group (supercell phonons).
                If 0 or negative an exception is raised.
            - full_name : bool, optional
                If it is True, then the dynamical matrix is loaded without appending the q index.
                This is compatible only with gamma point matrices.
        """
        
        # Check if the nqirr is correct
        if nqirr <= 0:
            raise ValueError("Error, the specified nqirr is not valid: it must be positive!")

        if full_name and nqirr > 1:
            raise ValueError("Error, with full_name only gamma matrices are loaded.")

        # Initialize the atomic structure
        self.structure = Structure.Structure()
        
        # Start processing the dynamical matrices
        for iq in range(nqirr):
            # Check if the selected matrix exists
            if not full_name:
                filepath = "%s%i" % (fildyn_prefix, iq + 1)
            else:
                filepath = fildyn_prefix
                
            if not os.path.isfile(filepath):
                raise ValueError("Error, file %s does not exist." % filepath)
            
            # Load the matrix as a regular file
            dynfile = file(filepath, "r")
            dynlines = [line.strip() for line in dynfile.readlines()]
            dynfile.close()
            
            if (iq == 0):
                # This is a gamma point file, generate the structure
                # Go to the third line
                struct_info = dynlines[2].split()
                
                # Check if the ibrav is 0
                ibrav = int(struct_info[2])
                celldm = np.zeros(6)
                celldm[0] = float(struct_info[3])
                celldm[1] = float(struct_info[4])
                celldm[2] = float(struct_info[5])
                celldm[3] = float(struct_info[6])
                celldm[4] = float(struct_info[7])
                celldm[5] = float(struct_info[8])
                
#                if ibrav != 0:
#                    raise ValueError("Error, only ibrav 0 supported up to now")
                
                nat = int(struct_info[1])
                ntyp = int(struct_info[0])
                self.alat = float(struct_info[3]) * BOHR_TO_ANGSTROM # We want a structure in angstrom
                
                # Allocate the coordinates
                self.structure.N_atoms = nat
                self.structure.coords = np.zeros((nat, 3))
                
                # Read the unit cell
                unit_cell = np.zeros((3,3))
                if ibrav == 0:
                    for i in range(3):
                        unit_cell[i, :] = np.array([float(item) for item in dynlines[4 + i].split()]) * self.alat
                else:
                    unit_cell = Methods.get_unit_cell_from_ibrav(ibrav, celldm)
                    # Insert 4 lines to match the same number of lines as in ibrav = 0
                    dynlines.insert(3, "")
                    dynlines.insert(3, "")
                    dynlines.insert(3, "")
                    dynlines.insert(3, "")
                    
                # Read the atomic type
                atoms_dict = {}
                masses_dict = {}
                for atom_index in range(1, ntyp + 1):
                    atm_line = dynlines[6 + atom_index]
                    atoms_dict[atom_index] = atm_line.split("'")[1].strip()
                    
                    # Get also the atomic mass
                    masses_dict[atoms_dict[atom_index]] = float(atm_line.split("'")[-1].strip())
                    
                self.structure.set_masses(masses_dict)
                
                
                self.structure.unit_cell = unit_cell
                self.structure.has_unit_cell = True
                
                # Read the atoms
                for i in range(nat):
                    # Jump the lines up to the structure
                    line_index = 7 + ntyp + i
                    atom_info = np.array([float(item) for item in dynlines[line_index].split()])
                    self.structure.atoms.append(atoms_dict[int(atom_info[1])])
                    self.structure.coords[i, :] = atom_info[2:] * self.alat
                    
                
            # From now start reading the dynamical matrix -----------------------
            reading_dyn = True
            q_star = []
            
            # Pop the beginning of the matrix
            while reading_dyn:      
                # Pop the file until you reach the dynamical matrix
                if "cartesian axes" in dynlines[0]:
                    reading_dyn = False
                dynlines.pop(0)
                
            # Get the small q point
            reading_dyn = True
            index = -1
            current_dyn = np.zeros((3*self.structure.N_atoms, 3*self.structure.N_atoms), dtype = np.complex64)    
            
            # The atom indices
            atm_i = 0
            atm_j = 0
            coordline = 0
            
            dielectric_read = 0
            pol_read = 0
            
            # Info about what I'm reading
            reading_dielectric = False
            reading_eff_charges = False
            reading_raman = False
            
            while reading_dyn:
                # Advance in the reading
                index += 1
                
                # Setup what I'm reading
                if "Diagonalizing" in dynlines[index]:
                    reading_dyn = False
                    self.dynmats.append(current_dyn.copy())

                    continue
                if "Dielectric" in dynlines[index]:
                    reading_dielectric = True
                    reading_eff_charges = False
                    reading_raman = False
                    
                    # Reset the dielectric tensor
                    self.dielectric_tensor = np.zeros((3,3))
                    dielectric_read = 0
                    
                    continue
                elif "Effective" in dynlines[index]:
                    reading_dielectric = False
                    reading_eff_charges = True
                    reading_raman = False
                
                    
                    # Reset the effective charges
                    self.effective_charges = np.zeros((self.structure.N_atoms, 3, 3))
                    
                    continue
                elif  "Raman" in dynlines[index]:
                    reading_dielectric = False
                    reading_eff_charges = False
                    reading_raman = True
                    
                    # Reset the raman tensor
                    self.raman_tensor = np.zeros((3,3, 3*self.structure.N_atoms))
                    continue
                elif "q = " in dynlines[index]:
                    #Read the q
                    qpoint = np.array([float(item) for item in dynlines[index].replace("(", ")").split(')')[1].split()])
                    q_star.append(qpoint)
                    self.q_tot.append(qpoint)
                    reading_dielectric = False
                    reading_eff_charges = False
                    reading_raman = False
                    continue
                elif "ynamical" in dynlines[index]:
                    # Save the dynamical matrix
                    self.dynmats.append(current_dyn.copy())
                    reading_dielectric = False
                    reading_eff_charges = False
                    reading_raman = False
                    continue
                    
                
                # Read what is needed
                numbers_in_line = dynlines[index].split()
                if len(numbers_in_line) == 0:
                    continue
                
                if reading_dielectric:
                    # Reading the dielectric
                    if len(numbers_in_line) == 3:
                        self.dielectric_tensor[dielectric_read, :] = np.array([float(x) for x in numbers_in_line])
                        dielectric_read += 1
                elif reading_eff_charges:
                    if numbers_in_line[0].lower() == "atom":
                        atm_i = int(numbers_in_line[2]) - 1
                        dielectric_read = 0
                    elif len(numbers_in_line) == 3:
                        self.effective_charges[atm_i, dielectric_read,:] = np.array([float(x) for x in numbers_in_line])
                        dielectric_read += 1
                elif reading_raman:
                    if numbers_in_line[0].lower() == "atom":
                        atm_i = int(numbers_in_line[2]) - 1
                        pol_read = int(numbers_in_line[4]) - 1
                        dielectric_read = 0
                    elif len(numbers_in_line) == 3:
                        self.raman_tensor[dielectric_read,:, 3*atm_i + pol_read] = np.array([float(x) for x in numbers_in_line])
                        dielectric_read += 1
                else:
                    # Read the numbers
                    if (len(numbers_in_line) == 2):
                        # Setup which atoms are 
                        atm_i = int(numbers_in_line[0]) - 1
                        atm_j = int(numbers_in_line[1]) - 1
                        coordline = 0
                    elif(len(numbers_in_line) == 6):
                        # Read the dynmat
                        for k in range(3):
                            current_dyn[3 * atm_i + coordline, 3*atm_j + k] = float(numbers_in_line[2*k]) + 1j*float(numbers_in_line[2*k + 1])
                        coordline += 1
                
                
            # Append the new stars for the irreducible q point
            self.q_stars.append(q_star)
        
        # Ok, the matrix has been initialized
        self.initialized = True
        
    def DyagDinQ(self, iq):
        """
        Dyagonalize the dynamical matrix in the given q point index.
        This methods returns both frequencies and polarization vectors.
        The frequencies and polarization are ordered. Negative frequencies are to
        be interpreted as instabilities and imaginary frequency, as for QE.
        
        They are returned 
        
        Parameters
        ----------
            - iq : int
                Tbe index of the q point of the matrix to be dyagonalized.
                
        Results
        -------
            - frequencies : ndarray (float)
                The frequencies (square root of the eigenvalues divided by the masses).
                These are in Ry units.
            - pol_vectors : ndarray (N_modes x 3)^2
                The polarization vectors for the dynamical matrix. They are returned
                in a Fortran fashon order: pol_vectors[:, i] is the i-th polarization vector.
        """
        
        
        
        # First of all get correct dynamical matrix by dividing per the masses.
        real_dyn = np.zeros((3* self.structure.N_atoms, 3*self.structure.N_atoms), dtype = np.complex64)
        for i, atm_type1 in enumerate(self.structure.atoms):
            m1 = self.structure.masses[atm_type1]
            for j, atm_type2 in enumerate(self.structure.atoms):
                m2 = self.structure.masses[atm_type2]
                real_dyn[3*i : 3*i + 3, 3*j : 3*j + 3] = 1 / np.sqrt(m1 * m2)
        

        real_dyn *= self.dynmats[iq]
        
        eigvals, pol_vects = np.linalg.eig(real_dyn)
        
        f2 = np.real(eigvals)
        
        # Check for imaginary frequencies (unstabilities) and return them as negative
        frequencies = np.zeros(len(f2))
        frequencies[f2 > 0] = np.sqrt(f2[f2 > 0])
        frequencies[f2 < 0] = -np.sqrt(-f2[f2 < 0])
        
        # Order the frequencies and the polarization vectors
        sorting_mask = np.argsort(frequencies)
        frequencies = frequencies[sorting_mask]
        pol_vects = pol_vects[:, sorting_mask]
        
        return frequencies, pol_vects
    
    def Copy(self):
        """
        Return an exact copy of itself. 
        This will implies copying all the dynamical matricies and structures inside.
        So take care if the structure is big, because it will overload the memory.
        """
        
        ret = Phonons()
        ret.structure = self.structure.copy()
        ret.q_tot = self.q_tot
        ret.nqirr = self.nqirr
        ret.initialized = self.initialized
        ret.q_stars = self.q_stars
        
        for i, dyn in enumerate(self.dynmats):
            ret.dynmats.append(dyn.copy())
        
        return ret
    
    def CheckCompatibility(self, other):
        """
        This function checks the compatibility between two dynamical matrices.
        The check includes the number of atoms and the atomic type.

        Parameters
        ----------
            - other : Phonons.Phonons()
                The other dynamical matrix to check the compatibility.
                
        Returns
        -------
            bool 
        """
        
        # First of all, check if other is a dynamical matrix:
        if type(other) != type(self):
            return False
        
        # Check if the two structures shares the same number of atoms:
        if self.structure.N_atoms != other.structure.N_atoms:
            return False
        
        # Check if they belong to the same supercell:
        if self.nqirr != other.nqirr:
            return False
        
        # Then they are compatible
        return True
    
    def GetUpsilonMatrix(self, T):
        """
        This subroutine returns the inverse of the correlation matrix.
        It is computed as following
        
        .. math::
            
            \\Upsilon_{ab} = \\sqrt{M_aM_b}\\sum_\\mu \\frac{2\\omega_\\mu}{(1 + n_\\mu)\\hbar} e_\\mu^a e_\\mu^b
            
        It is used to compute the probability of a given atomic displacement.
        The resulting matrix is a 3N x 3N one ordered as the dynamical matrix here.
        
        NOTE: only works for the gamma point.
        
        Parameters
        ----------
            T : float
                Temperature of the calculation (Kelvin)
        
        Returns
        -------
            ndarray(3N x3N)
                The inverse of the correlation matrix.
        """
        K_to_Ry=6.336857346553283e-06

        if T < 0:
            raise ValueError("Error, T must be posititive (or zero)")
        
        if self.nqirr != 1:
            raise ValueError("Error, this function yet not supports the supercells.")
        
        # We need frequencies and polarization vectors
        w, pols = self.DyagDinQ(0)
        
        # Transform the polarization vector into real one
        pols = np.real(pols)
        
        # Discard translations
        w = w[3:]
        pols = pols[:, 3:]
        
        # Get the bosonic occupation number
        nw = np.zeros(np.shape(w))
        if T == 0:
            nw = 0.
        else:
            nw =  1. / (np.exp(w/(K_to_Ry * T)) -1)
        
        # Compute the matrix
        factor = 2 * w / (1. + 2*nw)
        Upsilon = np.einsum( "i, ji, ki", factor, pols, pols)
        
        # Get the masses for the final multiplication
        mass1 = np.zeros( 3*self.structure.N_atoms)
        for i in range(self.structure.N_atoms):
            mass1[ 3*i : 3*i + 3] = np.sqrt(self.structure.masses[ self.structure.atoms[i]])
        
        _m1_ = np.tile(mass1, (3 * self.structure.N_atoms, 1))
        _m2_ = np.tile(mass1, (3 * self.structure.N_atoms, 1)).transpose()
        
        return Upsilon * _m1_ * _m2_
    
    
    def GetProbability(self, displacement, T, upsilon_matrix = None, normalize = True):
        """
        This function, given a particular displacement, returns the probability density
        of finding the system around that displacement. This in practical computes 
        density matrix of the system in this way
        
        .. math::
            
            \\rho(\\vec u) = \\sqrt{\\det(\\Upsilon / 2\\pi)} \\times \\exp\\left[-\\frac 12 \\sum_{ab} u_a \\Upsilon_{ab} u_b\\right]
            
        Where :math:`\\vec u` is the displacement, :math:`\\Upsilon` is the inverse of the covariant matrix
        computed through the method self.GetUpsilonMatrix().
        
        Parameters
        ----------
            displacement : ndarray(3xN) or ndarray(N, 3)
                The displacement on which you want to compute the probability.
                It can be both an array of dimension 3 x self.structure.N_atoms or
                a bidimensional array of structure (N_atoms, 3).
            T : float
                Temperature (Kelvin) for the calculation. It will be discarded 
                if a costum upsilon_matrix is provided.
            upsilon_matrix : ndarray (3xN)^2, optional
                If you have to compute many times this probability it can be convenient
                to compute only once the upsilon matrix, and recycle it. If it is
                None (as default) the upsilon matrix will be recomputed each time.
            normalize : bool, optional
                If false (default true) the probability distribution will not be normalized.
                Useful to check if the exponential weight is the same after some manipulation
                
        Returns
        -------
            float
                The probability density of finding the system in the given displacement.
                
        """
        
        disp = np.zeros( 3 * self.structure.N_atoms)
        
        # Reshape the displacement
        if len(np.shape(displacement)) == 2:
            disp = displacement.reshape( len(disp))
        else:
            disp = displacement
        
        
        if upsilon_matrix is None:
            upsilon_matrix = self.GetUpsilonMatrix(T)
        
        # Compute the braket
        braket = np.einsum("i, ij, j", disp, upsilon_matrix, disp)
        
        # Get the normalization
        vals = np.linalg.eigvals(upsilon_matrix)
        vals = vals[np.argsort(np.abs(vals))]
        
        vals /= 2*np.pi
        det = np.prod(vals[3:])
        
        if normalize:
            return  np.sqrt(det) * np.exp(-braket)
        else:
            return  np.exp(-braket)
    
    def GetRatioProbability(self, structure, T, dyn0, T0):
        """
        IMPORTANCE SAMPLING
        ===================
        
        This method compute the ration of the probability of extracting a given structure at temperature T
        generated with dyn0 at T0 if the extraction is made with the self dynamical matrix.
        
        It is very usefull to perform importance sampling tests.
        
        .. math::
            
            w(\\vec u) = \\frac{\\rho_{D_1}(\\vec u, T)}{\\rho_{D_0}(\\vec u, T_0)}
            
        Where :math:`D_1` is the current dynamical matrix, while :math:`D_0` is the
        dynamical matrix that has been actually used to generate dyn0
        
        Parameters
        ----------
            structure : Structure.Structure()
                The atomic structure generated according to dyn0 and T0 to evaluate the statistical significance ratio.
            T : float
                The target temperature
            dyn0 : Phonons.Phonons()
                The dynamical matrix used to generate the given structure.
            T0 : float
                The temperature used in the generation of the structure
        
        Results
        -------
            float
                The ratio :math:`w(\\vec u)` between the probabilities.
        """
        
        
        # Get the displacement respect the two central atomic positions
        disp1 = structure.get_displacement(self.structure)
        disp0 = structure.get_displacement(dyn0.structure)
        
        # TODO: Improve the method with a much more reliable one
        # In fact the ratio between them is much easier (this can be largely affected by rounding)
        return self.GetProbability(disp1, T) / dyn0.GetProbability(disp0, T0)
    
    def GetStrainMatrix(self, new_cell, T = 0):
        """
        STRAIN THE DYNAMICAL MATRIX
        ===========================
        
        This function strains the dynamical matrix to fit into the new cell.
        It will modify both the polarization vectors and the frequencies.
        
        The strain is performed on the covariance matrix.
        
        .. math::
            
            {\\Upsilon_{axby}^{-1}}' = \\sum_{\\alpha,\\beta = x,y,z} \\varepsilon_{x\\alpha}\\varepsilon_{y\\beta}\\Upsilon_{a\\alpha b\\beta}^{-1}
        
        Then the new :math:`\\Upsilon^{-1}` matrix is diagonalized, eigenvalues and eigenvector are built,
        and from them the new dynamical matrix is computed.
        
        NOTE: This works only at Gamma
        
        Parameters
        ----------
            new_cell : ndarray 3x3
                The new unit cell after the strain.
            T : float
                The temperature of the strain (default 0)
                
        Results
        -------
            dyn : Phonons.Phonons()
                A new dynamical matrix strained. Note, the current dynamical matrix will not be modified.
        """
        K_to_Ry=6.336857346553283e-06
        
        if T < 0:
            raise ValueError("Error, the temperature must be positive.")
        
        # Get the polarization vectors and frequencies
        w, pol_vects = self.DyagDinQ(0)
        
        n_modes = len(w)
        
        # Strain the polarization vectors
        new_vect = np.zeros(np.shape(pol_vects))
        for i in range(3, n_modes):
            for j in range(self.structure.N_atoms):
                # Get the crystal representation of the polarization vector
                cov_coord = Methods.covariant_coordinates(self.structure.unit_cell, 
                                                          pol_vects[3*j: 3*(j+1), i])
                
                # Transform the crystal representation into the cartesian in the new cell
                new_vect[3*j: 3*(j+1), i] = np.einsum("ij, i", new_cell, cov_coord)
        
        # Now prepare the new Covariance Matrix
        factor = np.zeros(n_modes)
        if T == 0:
            factor[3:] = 1 / (2. * w[3:])
        else:
            n = 1 / (np.exp(w[3:] / (K_to_Ry * T)) - 1)
            factor[3:] = (1. + n) / (2*w[3:])
        
        cmat = np.einsum("i, hi,ki", factor, new_vect, new_vect)
        
        # Diagonalize once again
        newf, new_pols = np.linalg.eig(cmat)
#        
#        # DEBUG PRINT
#        prova1 = np.sort(newf)
#        prova2 = np.sort(factor)
#        for i in range(n_modes):
#            print "New: %e | Old: %e" % (prova1[i], prova2[i])
#        
        
        # Sort the results
        sort_mask = np.argsort(newf)
        newf = newf[sort_mask]
        new_pols = new_pols[:, sort_mask]
        
        # Initialize the array of the new frequencies
        new_w = np.zeros(n_modes)
        new_w[3:] = 1. / (2 * newf[3:])
        
        # Sort once again
        sort_mask = np.argsort(new_w)
        new_w = new_w[sort_mask]
        new_pols = new_pols[:, sort_mask]
        
        
        # If the temperature is different from zero, we must obtain a new frequency
        # using a numerical nonlinear solver
        if T != 0:
            def opt_func(w):
                return 2*w*newf - 1./( 1 - np.exp(w / (K_to_Ry * T)))
            
            new_w = scipy.optimize.anderson(opt_func, new_w)
#        
#        print "Compare frequencies:"
#        for i in range(0,n_modes):
#            print "New: %e | Old: %e" % (new_w[i], w[i])
            
        # Now we can rebuild the dynamical matrix
        out_dyn = self.Copy()
        out_dyn.structure.change_unit_cell(new_cell)
        out_dyn.dynmats[0] = np.einsum("i, hi, ki", new_w**2, new_pols, new_pols)
        
        # Get the masses for the final multiplication
        mass1 = np.zeros( 3*self.structure.N_atoms)
        for i in range(self.structure.N_atoms):
            mass1[ 3*i : 3*i + 3] = self.structure.masses[ self.structure.atoms[i]]
        
        _m1_ = np.tile(mass1, (3 * self.structure.N_atoms, 1))
        _m2_ = np.tile(mass1, (3 * self.structure.N_atoms, 1)).transpose()
        
        out_dyn.dynmats[0] *= np.sqrt( _m1_ * _m2_ )
        
        return out_dyn
        
        
    def save_qe(self, filename, full_name = False):
        """
        SAVE THE DYNMAT
        ===============
        
        This subroutine saves the dynamical matrix in the quantum espresso file format.
        The dynmat is the force constant matrix in Ry units.
        
        .. math::
            
            \\Phi_{ab} = \\sum_\\mu \\omega_\\mu^2 e_\\mu^a e_\\mu^b \\sqrt{M_a M_b}
            
        Where :math:`\\Phi_{ab}` is the force constant matrix between the a-b atoms (also cartesian
        indices), :math:`\\omega_\\mu` is the phonon frequency and :math:`e_\\mu` is the
        polarization vector.
        
        
        Parameters
        ----------
            filename : string
                The path in which the quantum espresso dynamical matrix will be written.
            full_name : bool
                If true only the gamma matrix will be saved, and the irreducible q
                point index will not be appended. Otherwise all the file filenameIQ 
                where IQ is an integer between 0 and self.nqirr will be generated.
                filename0 will contain all the information about the Q points and the supercell.
        """
        A_TO_BOHR = 1.889725989
        RyToCm=109737.37595
        RyToTHz=3289.84377
        
        # Check if all the dynamical matrix must be saved, or only the 
        nqirr = self.nqirr
        if full_name:
            nqirr = 1
        
        # The following counter counts the total number of q points
        count_q = 0
        for iq in range(nqirr):
            # Prepare the file name appending the q point index
            fname = filename
            if not full_name:
                fname += str(iq+1)
            
            # Open the file
            fp = file(fname, "w")
            fp.write("Dynamical matrix file\n")
        
            # Get the different number of types
            types = []
            n_atoms = self.structure.N_atoms
            for i in range(n_atoms):
                if not self.structure.atoms[i] in types:
                    types.append(self.structure.atoms[i])
            n_types = len(types)
        
            # Assign an integer for each atomic species
            itau = {}
            for i in range(n_types):
                itau[types[i]] = i +1
            
            # Write the comment line
            fp.write("File generated with the CellConstructor by Lorenzo Monacelli\n")
            fp.write("%d %d %d %.8f %.8f %.8f %.8f %.8f %.8f\n" %
                     (n_types, n_atoms, 0, self.alat * A_TO_BOHR, 0, 0, 0, 0, 0) )
        
            # Write the basis vector
            fp.write("Basis vectors\n")
            # Get the unit cell
            for i in range(3):
                fp.write(" ".join("%12.8f" % x for x in self.structure.unit_cell[i,:] / self.alat) + "\n")
        
            # Set the atom types and masses
            for i in range(n_types):
                fp.write("\t%d  '%s '  %.8f\n" % (i +1, types[i], self.structure.masses[types[i]]))
        
            # Setup the atomic structure
            for i in range(n_atoms):
                # Convert the coordinates in alat
                coords = self.structure.coords[i,:] / self.alat
                fp.write("%5d %5d %15.10f %15.10f %15.10f\n" %
                         (i +1, itau[self.structure.atoms[i]], 
                          coords[0], coords[1], coords[2]))
        
            # Iterate over all the q points in the star
            nqstar = len(self.q_stars[iq])
            q_star = self.q_stars[iq]
            
            # Store the first matrix index of the star
            # This will be used to dyagonalize the matrix in the end of the file
            dyag_q_index = count_q
            
            for jq in range(nqstar):
                # Here the dynamical matrix starts
                fp.write("\n")
                fp.write("     Dynamical Matrix in cartesian axes\n")
                fp.write("\n")
                fp.write("     q = (    %.9f   %.9f   %.9f )\n" % 
                         (q_star[jq][0], q_star[jq][1], q_star[jq][2]))
                fp.write("\n")
            
                # Now print the dynamical matrix
                for i in range(n_atoms):
                    for j in range(n_atoms):
                        # Write the atoms
                        fp.write("%5d%5d\n" % (i + 1, j + 1))
                        for x in range(3):
                            line = "%12.8f%12.8f   %12.8f%12.8f   %12.8f%12.8f" % \
                                   ( np.real(self.dynmats[count_q][3*i + x, 3*j]), np.imag(self.dynmats[count_q][3*i + x, 3*j]),
                                     np.real(self.dynmats[count_q][3*i + x, 3*j+1]), np.imag(self.dynmats[count_q][3*i+x, 3*j+1]),
                                     np.real(self.dynmats[count_q][3*i + x, 3*j+2]), np.imag(self.dynmats[count_q][3*i+x, 3*j+2]) )
            
                            fp.write(line +  "\n")
                
                # Go to the next q point
                count_q += 1
        
            # Print the diagnoalization of the matrix
            fp.write("\n")
            fp.write("     Diagonalizing the dynamical matrix\n")
            fp.write("\n")
            fp.write("     q = (    %.9f   %.9f   %.9f )\n" % 
                     (q_star[0][0], q_star[0][1], q_star[0][2]))
            fp.write("\n")
            fp.write("*" * 75 + "\n")
            
            # Diagonalize the dynamical matrix
            freqs, pol_vects = self.DyagDinQ(dyag_q_index)
            nmodes = len(freqs)
            for mu in range(nmodes):
                # Print the frequency
                fp.write("%7s (%5d) = %14.8f [THz] = %14.8f [cm-1]\n" %
                         ("freq", mu+1, freqs[mu] * RyToTHz, freqs[mu] * RyToCm))
                
                # Print the polarization vectors
                for i in range(n_atoms):
                    fp.write("( %10.6f%10.6f %10.6f%10.6f %10.6f%10.6f )\n" %
                             (np.real(pol_vects[3*i, mu]), np.imag(pol_vects[3*i,mu]),
                              np.real(pol_vects[3*i+1, mu]), np.imag(pol_vects[3*i+1,mu]),
                              np.real(pol_vects[3*i+2, mu]), np.imag(pol_vects[3*i+1,mu])))
            fp.write("*" * 75 + "\n")
            fp.close()
            
            
            
    def ForcePositiveDefinite(self):
        """
        FORCE TO BE POSITIVE DEFINITE
        =============================
        
        This method force the matrix to be positive defined. 
        Usefull if you want to start with a matrix for a SCHA calculation.
        
        It will take the Dynamical matrix and rebuild it as
        
        .. math::
            
            \\Phi'_{ab} = \\sqrt{M_aM_b}\sum_{\mu} |\omega_\mu^2| e_\\mu^a e_\\mu^b 
            
        
        In this way the dynamical matrix will be always positive definite.
        """
        
        # Prepare the masses matrix
        mass1 = np.zeros( 3*self.structure.N_atoms)
        for i in range(self.structure.N_atoms):
            mass1[ 3*i : 3*i + 3] = self.structure.masses[ self.structure.atoms[i]]
        
        _m1_ = np.tile(mass1, (3 * self.structure.N_atoms, 1))
        _m2_ = np.tile(mass1, (3 * self.structure.N_atoms, 1)).transpose()
        
        for iq in range(len(self.dynmats)):
            # Diagonalize the matrix
            w, pols = self.DyagDinQ(iq)
            
            matrix = np.einsum("i, ji, ki", w**2, pols, pols) * np.sqrt(_m1_ * _m2_)
            self.dynmats[iq] = matrix
                        
                        
    def GetRamanResponce(self, pol_in, pol_out, T = 0):
        """
        RAMAN RESPONSE
        ==============
        
        Evaluate the raman response using the Mauri-Lazzeri equation.
        This subroutine needs the Raman tensor to be defined, and computes the intensity for each mode.
        It returns a list of intensity associated to each mode.
        
        .. math::
            
            I_{\\nu} = \\left| \\sum_{xy} \\epsilon_x^{(1)} A^\\nu_{xy} \\epsilon_y^{(2)}\\right|^2 \\frac{n_\\nu + 1}}{\\omega_\\nu}
    
        Where :math:`\\epsilon` are the polarization vectors of the incoming/outcoming light, :math:`n_\\nu` is the bosonic
        occupation number associated to the :math:`\\nu` mode, and :math:`A^\\nu_{xy}` is the Raman tensor in the mode rapresentation
    
        Parameters
        ----------
            pol_in : ndarray 3
                The polarization versor of the incominc electric field
            pol_out : ndarray 3
                The polarization versor of the outcoming electric field
            T : float
                The tempearture of the calculation
        
        Results
        -------
            ndarray (nmodes)
                Intensity for each mode of the current dynamical matrix.
        """
        
        K_to_Ry=6.336857346553283e-06
        
        
        if self.raman_tensor == None:
            raise ValueError("Error, to get the raman responce the raman tensor must be defined")
        
        w, pol_vects = self.DyagDinQ(0)
        
        # Get the mass array
        _m_ = np.zeros( 3*self.structure.N_atoms)
        for i in range(self.structure.N_atoms):
            _m_[ 3*i : 3*i + 3] = self.structure.masses[ self.structure.atoms[i]]
            
        
        # The super sum
        #print np.shape(self.raman_tensor), np.shape(pol_vects), np.shape(_m_), np.shape(pol_in), np.shape(pol_out)
        I = np.einsum("ijk, kl, k, i, j", self.raman_tensor, pol_vects, _m_, pol_in, pol_out)
        
        # Get the bosonic occupation number
        n = np.zeros(len(w))
        if T > 0:            
            beta = 1 / (K_to_Ry*T)
            n = 1 / (np.exp(beta * w) - 1.)
        
        return np.abs(I**2) * (1. + n) / w
            
            
            
    def ExtractRandomStructures(self, size=1, T=0, isolate_atoms = []):
        """
        EXTRACT RANDOM STRUCTURES
        =========================
        
        This method is used to extract a pool of random structures according to the current dinamical matrix.
        
        NOTE: for now available only at gamma
        
        Parameters
        ----------
            size : int
                The number of structures to be generated
            T : float
                The temperature for the generation of the ensemble
            isolate_atoms : list, optional
                A list of the atom index. Only the specified atoms are present in the output structure and displaced.
                This is very usefull if you want to measure properties of a particular region of the structure.
                By default all the atoms are used.
        
        Returns
        -------
            list
                A list of Structure.Structure()
        """
        K_to_Ry=6.336857346553283e-06
        BOHR_TO_ANG = 0.529177249

        
        if self.nqirr != 1:
            raise ValueError("Error, not yet implemented with supercells")
            
            
        # Check if isolate atoms is good
        if len(isolate_atoms):
            if np.max(isolate_atoms) >= self.structure.N_atoms:
                raise ValueError("Error, index in isolate_atoms out of boundary")
            
        # Now extract the values
        ws, pol_vects = self.DyagDinQ(0)
        
        # Remove translations
        ws = ws[3:]
        pol_vects = pol_vects[:, 3:]
        
        
        
        n_modes = len(ws)
        if T == 0:
            a_mu = 1 / np.sqrt(2* ws) * BOHR_TO_ANG
        else:            
            beta = 1 / (K_to_Ry*T)
            a_mu = 1 / np.sqrt( np.tanh(beta*ws / 2) *2* ws) * BOHR_TO_ANG
        
        # Prepare the coordinates
        total_coords = np.zeros((size, self.structure.N_atoms,3))
        
        # Prepare the random numbers
        rand = np.random.normal(size = (size, n_modes))
        
        # Get the masses for the final multiplication
        mass1 = np.zeros( 3*self.structure.N_atoms)
        for i in range(self.structure.N_atoms):
            mass1[ 3*i : 3*i + 3] = self.structure.masses[ self.structure.atoms[i]]
            
        total_coords = np.einsum("ij, j, kj", np.real(pol_vects), a_mu, rand)
        
        # Prepare the structures
        final_structures = []
        for i in range(size):
            tmp_str = self.structure.copy()
            # Prepare the new atomic positions 
            for k in range(tmp_str.N_atoms):
                tmp_str.coords[k,:] += total_coords[3*k : 3*(k+1), i] / np.sqrt(self.structure.masses[self.structure.atoms[k]])
            
            # Check if you must to pop some atoms:
            if len (isolate_atoms):
                
                tmp_str.N_atoms = len(isolate_atoms)
                new_coords = tmp_str.coords.copy()
                for j, x in enumerate(isolate_atoms):
                    tmp_str.coords[j,:] = new_coords[x,:]
            final_structures.append(tmp_str)
        
        
        return final_structures

    def get_energy_forces(self, structure, vector1d = False):
        """
        COMPUTE ENERGY AND FORCES
        =========================
        
        This subroutine computes the harmonic energy and the forces z
        for the given dynamical matrix at harmonic level.
        
        .. math::
            
            E = \frac 12 \\sum_{\\alpha\\beta} \\left(r_{\\alpha} - r^0_{\\alpha}\\right)\\Phi_{\\alpha\\beta} \\left(r_\\beta - r^0_\\beta\right)
            
            F_\\alpha = \\sum_{\\beta} \\Phi_{\\alpha\\beta} \\left(r_\\beta - r^0_\\beta\right)
            
        The energy is given in Rydberg, while the force is given in Ry/Angstrom
        
        NOTE: In this very moment it works only with gamma structures (unit cell)
        
        Parameters
        ----------
            structure : Structure.Structure()
                A unit cell structure in which energy and forces on atoms are computed
            vector1d : bool, optional
                If true the forces are returned in a reshaped 1d vector.
        
        Returns
        -------
            energy : float
                The harmonic energy (in Ry) of the structure
            force : ndarray N_atoms x 3
                The harmonic forces that acts on each atoms (in Ry / A)
        """
        
        # Convert the displacement vector in bohr
        A_TO_BOHR=1.889725989
        
        # Get the displacement vector (bohr)
        rv = structure.get_displacement(self.structure).reshape(structure.N_atoms * 3) * A_TO_BOHR
        
        # Get the energy
        energy = 0.5 * rv.dot ( self.dynmats[0].dot(rv))
        
        # Get the forces (Ry/ A)
        forces = self.dynmats[0].dot(rv) * A_TO_BOHR

        if not vector1d:
            forces = forces.reshape( (self.structure.N_atoms, 3))
        
        return energy, forces
        
        
