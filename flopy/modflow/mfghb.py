"""
mfghb module.  Contains the ModflowGhb class. Note that the user can access
the ModflowGhb class as `flopy.modflow.ModflowGhb`.

Additional information for this MODFLOW package can be found at the `Online
MODFLOW Guide
<http://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/index.html?ghb.htm>`_.

"""
from numpy import atleast_2d
from flopy.mbase import Package
from flopy.utils.util_list import mflist

class ModflowGhb(Package):
    """
    MODFLOW General-Head Boundary Package Class.

    Parameters
    ----------
    model : model object
        The model object (of type :class:`flopy.modflow.mf.Modflow`) to which
        this package will be added.
    ighbcb : int
        is a flag and a unit number. (the default is 0).
    layer_row_column_data : list of records
        In its most general form, this is a triple list of ghb records  The
        innermost list is the layer, row, column, stage, and conductance for a
        single ghb.  Then for a stress period, there can be a list of ghbs.
        Then for a simulation, there can be a separate list for each stress
        period. This gives the form of
            lrcd = [
                     [  #stress period 1
                       [l1, r1, c1, stage1, cond1],
                       [l2, r2, c2, stage2, cond2],
                       [l3, r3, c3, stage3, cond3],
                       ],
                     [  #stress period 2
                       [l1, r1, c1, stage1, cond1],
                       [l2, r2, c2, stage2, cond2],
                       [l3, r3, c3, stage3, cond3],
                       ], ...
                     [  #stress period kper
                       [l1, r1, c1, stage1, cond1],
                       [l2, r2, c2, stage2, cond2],
                       [l3, r3, c3, stage3, cond3],
                       ],
                    ]
        Note that if there are not records in layer_row_column_data, then the
        last group of ghbs will apply until the end of the simulation.
    layer_row_column_head_cond : list of records
        Deprecated - use layer_row_column_data instead.
    options : list of strings
        Package options. (default is None).
    naux : int
        number of auxiliary variables
    extension : string
        Filename extension (default is 'ghb')
    unitnumber : int
        File unit number (default is 23).
    zerobase : boolean (default is True)
        True when zero-based indices are used: layers, rows, columns start at 0
        False when one-based indices are used: layers, rows, columns start at 1 (deprecated)

    Attributes
    ----------
    mxactb : int
        Maximum number of ghbs for a stress period.  This is calculated
        automatically by FloPy based on the information in
        layer_row_column_data.

    Methods
    -------

    See Also
    --------

    Notes
    -----
    Parameters are not supported in FloPy.

    Examples
    --------

    >>> import flopy
    >>> m = flopy.modflow.Modflow()
    >>> lrcd = [[[2, 3, 4, 10., 100.]]]  #this well will be applied to all
    >>>                                  #stress periods
    >>> ghb = flopy.modflow.ModflowGhb(m, layer_row_column_data=lrcd)

    """
    def __init__(self, model, ipakcb=0, stress_period_data=None,dtype=None,
                 no_print=False, options=None,
                 extension='ghb', unitnumber=23):
        Package.__init__(self, model, extension, 'GHB',
                         unitnumber)  # Call ancestor's init to set self.parent, extension, name and unit number
        self.heading = '# GHB for MODFLOW, generated by Flopy.'
        self.url = 'ghb.htm'
        self.ipakcb = ipakcb  # no cell by cell terms are written
        self.no_print = no_print
        self.np = 0
        if options is None:
            options = []
        if self.no_print:
            options.append('NOPRINT')
        self.options = options
        self.parent.add_package(self)
        if dtype is not None:
            self.dtype = dtype
        else:
            self.dtype = self.get_default_dtype()
        self.stress_period_data = mflist(model,self.dtype,stress_period_data)

    def __repr__(self):
        return 'GHB package class'

    def ncells(self):
        # Returns the  maximum number of cells that have a well (developped for MT3DMS SSM package)
        return self.stress_period_data.mxact

    def write_file(self):
        f_ghb = open(self.fn_path, 'w')
        f_ghb.write('%s\n' % self.heading)
        f_ghb.write('%10i%10i' % (self.stress_period_data.mxact, self.ipakcb))
        for option in self.options:
            f_ghb.write('  {}'.format(option))
        f_ghb.write('\n')
        self.stress_period_data.write_transient(f_ghb)
        f_ghb.close()

    def add_record(self,kper,index,values):
        try:
            self.stress_period_data.add_record(kper,index,values)
        except Exception as e:
            raise Exception("mfghb error adding record to list: "+str(e))

    @staticmethod
    def get_empty(ncells=0,aux_names=None):
        #get an empty recaray that correponds to dtype
        dtype = ModflowGhb.get_default_dtype()
        if aux_names is not None:
            dtype = Package.add_to_dtype(dtype,aux_names,np.float32)
        d = np.zeros((ncells,len(dtype)),dtype=dtype)
        d[:,:] = -1.0E+10
        return np.core.records.fromarrays(d.transpose(),dtype=dtype)

    @staticmethod
    def get_default_dtype():
        dtype = np.dtype([("k",np.int),("i",np.int),\
                         ("j",np.int),("bhead",np.float32),\
                        ("cond",np.float32)])
        return dtype

    @staticmethod
    def load(f, model, nper=None, ext_unit_dict=None):
        """
        Load an existing package.

        Parameters
        ----------
        f : filename or file handle
            File to load.
        model : model object
            The model object (of type :class:`flopy.modflow.mf.Modflow`) to
            which this package will be added.
        nper : int
            The number of stress periods.  If nper is None, then nper will be
            obtained from the model object. (default is None).
        ext_unit_dict : dictionary, optional
            If the arrays in the file are specified using EXTERNAL,
            or older style array control records, then `f` should be a file
            handle.  In this case ext_unit_dict is required, which can be
            constructed using the function
            :class:`flopy.utils.mfreadnam.parsenamefile`.

        Returns
        -------
        rch : ModflowGhb object
            ModflowGhb object.

        Examples
        --------

        >>> import flopy
        >>> m = flopy.modflow.Modflow()
        >>> ghb = flopy.modflow.ModflowGhb.load('test.ghb', m)

        """
        if type(f) is not file:
            filename = f
            f = open(filename, 'r')
        # dataset 0 -- header
        while True:
            line = f.readline()
            if line[0] != '#':
                break
        # --check for parameters
        if "parameter" in line.lower():
            raw = line.strip().split()
            assert int(raw[1]) == 0, "Parameters are not supported"
            line = f.readline()
        #dataset 2a
        #dataset 2a
        t = line.strip().split()
        ipakcb = 0
        try:
            if int(t[1]) != 0:
                ipakcb = 53
        except:
            pass
        options = []
        aux_names = []
        if len(t) > 2:
            it = 2
            while it < len(t):
                toption = t[it]
                print it,t[it]
                if toption.lower() is 'noprint':
                    options.append(toption)
                elif 'aux' in toption.lower():
                    options.append(' '.join(t[it:it+2]))
                    aux_names.append(t[it+1].lower())
                    it += 1
                it += 1
        if nper is None:
            nrow, ncol, nlay, nper = model.get_nrow_ncol_nlay_nper()
        #read data for every stress period
        stress_period_data = {}
        for iper in xrange(nper):
            print "   loading GHB for kper {0:5d}".format(iper+1)
            line = f.readline()
            if line == '':
                break
            t = line.strip().split()
            itmp = int(t[0])
            if itmp == 0 or itmp == -1:
                stress_period_data[iper] = itmp
            elif itmp > 0:
                current = ModflowGhb.get_empty(itmp,aux_names=aux_names)
                for ibnd in xrange(itmp):
                    line = f.readline()
                    if "open/close" in line.lower():
                        raise NotImplementedError("load() method does not support \'open/close\'")
                    t = line.strip().split()
                    current[ibnd] = tuple(t[:len(current.dtype.names)])
                stress_period_data[iper] = current
        ghb = ModflowGhb(model, ipakcb=ipakcb,
                         stress_period_data=stress_period_data,\
                         dtype=ModflowGhb.get_empty(0,aux_names=aux_names).dtype,\
                         options=options)
        return ghb







        t = line.strip().split()
        mxactb = int(t[0])
        ighbcb = None
        ighncb = 0
        try:
            if int(t[1]) != 0:
                ighbcb = 53
        except:
            pass

        options = []
        naux = 0
        if len(t) > 2:
            for toption in t[3:-1]:
                if toption.lower() is 'noprint':
                    options.append(toption)
                elif 'aux' in toption.lower():
                    naux += 1
                    options.append(toption)
        if nper is None:
            nrow, ncol, nlay, nper = model.get_nrow_ncol_nlay_nper()
        #read data for every stress period
        layer_row_column_data = []
        current = []
        nitems = 5 + naux
        for iper in xrange(nper):
            print "   loading ghbs for kper {0:5d}".format(iper + 1)
            line = f.readline()
            t = line.strip().split()
            itmp = int(t[0])
            if itmp == 0:
                current = []
            elif itmp > 0:
                for ibnd in xrange(itmp):
                    line = f.readline()
                    t = line.strip().split()
                    bnd = []
                    for jdx in xrange(nitems):
                        if jdx < 3:
                            bnd.append(int(t[jdx]))
                        else:
                            bnd.append(float(t[jdx]))
                    current.append(bnd)
            layer_row_column_data.append(current)
        ghb = ModflowGhb(model, ighbcb=ighbcb,
                         layer_row_column_data=layer_row_column_data,
                         options=options, naux=naux)
        return ghb
