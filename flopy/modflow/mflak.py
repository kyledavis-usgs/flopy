"""
mflak module.  Contains the ModflowLak class. Note that the user can access
the ModflowLak class as `flopy.modflow.ModflowLak`.

Additional information for this MODFLOW package can be found at the `Online
MODFLOW Guide
<http://water.usgs.gov/ogw/modflow/MODFLOW-2005-Guide/lak.htm>`_.

"""
import os
import sys
import numpy as np
from ..pakbase import Package
from ..utils.util_array import Transient3d
from ..utils import Util3d, read_fixed_var, write_fixed_var


class ModflowLak(Package):
    """
    MODFLOW Lake Package Class.

    Parameters
    ----------
    model : model object
        The model object (of type :class:`flopy.modflow.mf.Modflow`) to which
        this package will be added.
    options : list of strings
        Package options. (default is None).
    extension : string
        Filename extension (default is 'lak')
    unitnumber : int
        File unit number (default is None).
    filenames : str or list of str
        Filenames to use for the package and the output files. If
        filenames=None the package name will be created using the model name
        and package extension and the cbc output name will be created using
        the model name and .cbc extension (for example, modflowtest.cbc),
        if ipakcbc is a number greater than zero. If a single string is passed
        the package will be set to the string and cbc output names will be
        created using the model name and .cbc extension, if ipakcbc is a
        number greater than zero. To define the names for all package files
        (input and output) the length of the list of strings should be 2.
        Default is None.

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
    >>> lak = {}
    >>> lak[0] = [[2, 3, 4, 15.6, 1050., -4]]  #this lake boundary will be
    >>>                                        #applied to all stress periods
    >>> lak = flopy.modflow.ModflowLak(m, nstress_period_data=strd)

    """

    def __init__(self, model, nlakes=1, ipakcb=None, theta=-1.,
                 nssitr=0, sscncr=0.0, surfdep=0., stages=1., stage_range=None,
                 tab_files=None, tab_units=None, lakarr=None, bdlknc=None,
                 sill_data=None, flux_data=None,
                 extension='lak', unitnumber=None, filenames=None,
                 options=None, **kwargs):
        """
        Package constructor.

        """
        # set default unit number of one is not specified
        if unitnumber is None:
            unitnumber = ModflowLak.defaultunit()

        # set filenames
        tabdata = False
        nlen = 2
        if options is not None:
            for option in options:
                if 'TABLEINPUT' in option.upper():
                    tabdata = True
                    nlen += nlakes
                    break
        if filenames is None:
            filenames = [None for x in range(nlen)]
        elif isinstance(filenames, str):
            filenames = [filenames] + [None for x in range(nlen - 1)]
        elif isinstance(filenames, list):
            if len(filenames) < nlen:
                filenames = filenames + [None for x in range(2, nlen)]

        # update external file information with cbc output, if necessary
        if ipakcb is not None:
            fname = filenames[1]
            model.add_output_file(ipakcb, fname=fname,
                                  package=ModflowLak.ftype())
        else:
            ipakcb = 0

        # table input files
        if tabdata:
            if tab_files is None:
                tab_files = filenames[2:]

        # add tab_files as external files
        if tabdata:
            # make sure the number of tabfiles is equal to the number of lakes
            if len(tab_files) < nlakes:
                msg = 'a tabfile must be specified for each lake' + \
                      '{} tabfiles specified '.format(len(tab_files)) + \
                      'instead of {} tabfiles'.format(nlakes)
            # make sure tab_files are not None
            for idx, fname in enumerate(tab_files):
                if fname is None:
                    msg = 'a filename must be specified for the ' + \
                          'tabfile for lake {}'.format(idx + 1)
                    raise ValueError(msg)
            # set unit for tab files if not passed to __init__
            if tab_units is None:
                tab_units = []
                for idx in range(len(tab_files)):
                    tab_units.append(model.next_ext_unit())
            # add tabfiles as external files
            for iu, fname in zip(tab_units, tab_files):
                model.add_external(fname, iu)

        # Fill namefile items
        name = [ModflowLak.ftype()]
        units = [unitnumber]
        extra = ['']

        # set package name
        fname = [filenames[0]]

        # Call ancestor's init to set self.parent, extension, name and unit number
        Package.__init__(self, model, extension=extension, name=name,
                         unit_number=units, extra=extra, filenames=fname)

        self.heading = '# {} package for '.format(self.name[0]) + \
                       ' {}, '.format(model.version_types[model.version]) + \
                       'generated by Flopy.'
        self.url = 'lak.htm'

        if options is None:
            options = []
        self.options = options
        self.nlakes = nlakes
        self.ipakcb = ipakcb
        self.theta = theta
        self.nssitr = nssitr
        self.sscncr = sscncr
        self.surfdep = surfdep
        if isinstance(stages, float):
            stages = np.array(self.nlakes, dtype=np.float) * stages
        elif isinstance(stages, list):
            stages = np.array(stages)
        if stages.shape[0] != nlakes:
            err = 'stages shape should be ' + \
                  '({}) but is only ({}).'.format(nlakes, stages.shape[0])
            raise Exception(err)
        self.stages = stages
        if stage_range is None:
            stage_range = np.ones((nlakes, 2), dtype=np.float)
            stage_range[:, 0] = -10000.
            stage_range[:, 1] = 10000.
        else:
            if isinstance(stage_range, list):
                stage_range = np.array(stage_range)
            elif isinstance(stage_range, float):
                err = 'stage_range should be a list or ' + \
                      'array of size ({}, 2)'.format(nlakes)
                raise Exception(err)
        if self.parent.dis.steady[0]:
            if stage_range.shape != (nlakes, 2):
                err = 'stages shape should be ' + \
                      '({},2) but is only {}.'.format(nlakes,
                                                      stage_range.shape)
                raise Exception(err)
        self.stage_range = stage_range

        # tabfile data
        self.tabdata = tabdata
        self.iunit_tab = tab_units

        if lakarr is None and bdlknc is None:
            err = 'lakarr and bdlknc must be specified'
            raise Exception(err)
        nrow, ncol, nlay, nper = self.parent.get_nrow_ncol_nlay_nper()
        self.lakarr = Transient3d(model, (nlay, nrow, ncol), np.int,
                                  lakarr, name='lakarr_')
        self.bdlknc = Transient3d(model, (nlay, nrow, ncol), np.float32,
                                  bdlknc, name='bdlknc_')

        if sill_data is not None:
            if not isinstance(sill_data, dict):
                try:
                    sill_data = {0: sill_data}
                except:
                    err = 'sill_data must be a dictionary'
                    raise Exception(err)

        if flux_data is not None:
            if not isinstance(flux_data, dict):
                # convert array to a dictionary
                try:
                    flux_data = {0: flux_data}
                except:
                    err = 'flux_data must be a dictionary'
                    raise Exception(err)
            for key, value in flux_data.items():
                if isinstance(value, np.ndarray):
                    td = {}
                    for k in range(value.shape[0]):
                        td[k] = value[k, :].aslist()
                    flux_data[key] = td
                    if len(list(flux_data.keys())) != nlakes:
                        err = 'flux_data dictionary must ' + \
                              'have {} entries'.format(nlakes)
                        raise Exception(err)
                elif isinstance(value, float) or \
                        isinstance(value, int):
                    td = {}
                    for k in range(self.nlakes):
                        td[k] = (np.ones(6, dtype=np.float) * value).aslist()
                    flux_data[key] = td
                elif isinstance(value, dict):
                    try:
                        steady = self.parent.dis.steady[key]
                    except:
                        steady = True
                    nlen = 4
                    if steady and key > 0:
                        nlen = 6
                    for k in range(self.nlakes):
                        td = value[k]
                        if len(td) < nlen:
                            err = 'flux_data entry for stress period'.format(
                                key + 1) + \
                                  'has {} entries but '.format(nlen) + \
                                  'should have {} entries'.format(len(td))
                            raise Exception(err)

        self.flux_data = flux_data
        self.sill_data = sill_data

        self.parent.add_package(self)

        return

    def ncells(self):
        # Return the  maximum number of cells that have a stream
        # (developed for MT3DMS SSM package)
        nrow, ncol, nlay, nper = self.parent.nrow_ncol_nlay_nper
        return (nlay * nrow * ncol)

    def write_file(self):
        """
        Write the package file.

        Returns
        -------
        None

        """
        f = open(self.fn_path, 'w')
        # dataset 0
        self.heading = '# {} package for '.format(self.name[0]) + \
                       '{}, generated by Flopy.'.format(self.parent.version)
        f.write('{0}\n'.format(self.heading))

        # dataset 1a
        if len(self.options) > 0:
            for option in self.options:
                f.write('{} '.format(option))
            f.write('\n')

        # dataset 1b
        f.write(write_fixed_var([self.nlakes, self.ipakcb],
                                free=self.parent.free_format_input))
        # dataset 2
        steady = np.any(self.parent.dis.steady.array)
        t = [self.theta]
        if self.theta < 0. or steady:
            t.append(self.nssitr)
            t.append(self.sscncr)
        if self.theta < 0.:
            t.append(self.surfdep)
        f.write(write_fixed_var(t, free=self.parent.free_format_input))

        # dataset 3
        steady = self.parent.dis.steady[0]
        for n in range(self.nlakes):
            ipos = [10]
            t = [self.stages[n]]
            if steady:
                ipos.append(10)
                t.append(self.stage_range[n, 0])
                ipos.append(10)
                t.append(self.stage_range[n, 1])
            if self.tabdata:
                ipos.append(5)
                t.append(self.iunit_tab[n])
            f.write(write_fixed_var(t, ipos=ipos,
                                    free=self.parent.free_format_input))

        ds8_keys = list(self.sill_data.keys())
        ds9_keys = list(self.flux_data.keys())
        nper = self.parent.dis.steady.shape[0]
        for kper in range(nper):
            itmp, file_entry_lakarr = self.lakarr.get_kper_entry(kper)
            ibd, file_entry_bdlknc = self.bdlknc.get_kper_entry(kper)

            itmp2 = 0
            if kper in ds9_keys:
                itmp2 = 1

            t = [itmp, itmp2, 1]
            comment = 'Stress period {}'.format(kper + 1)
            f.write(write_fixed_var(t, free=self.parent.free_format_input,
                                    comment=comment))

            if itmp > 0:
                f.write(file_entry_lakarr)
                f.write(file_entry_bdlknc)

                nslms = 0
                if kper in ds8_keys:
                    ds8 = self.sill_data[kper]
                    nslms = len(ds8)

                f.write(write_fixed_var([nslms], length=5,
                                        free=self.parent.free_format_input,
                                        comment='Data set 7'))
                if nslms > 0:
                    for n in range(nslms):
                        d1, d2 = ds8[n]
                        s = write_fixed_var(d1, length=5,
                                            free=self.parent.free_format_input,
                                            comment='Data set 8a')
                        f.write(s)
                        s = write_fixed_var(d2,
                                            free=self.parent.free_format_input,
                                            comment='Data set 8b')
                        f.write(s)

            if itmp2 > 0:
                ds9 = self.flux_data[kper]
                for n in range(self.nlakes):
                    try:
                        steady = self.parent.dis.steady[kper]
                    except:
                        steady = True
                    if kper > 0 and steady:
                        t = ds9[n]
                    else:
                        t = ds9[n][0:4]
                    s = write_fixed_var(t,
                                        free=self.parent.free_format_input,
                                        comment='Data set 9a')
                    f.write(s)

        # close the lak file
        f.close()

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
        str : ModflowStr object
            ModflowStr object.

        Examples
        --------

        >>> import flopy
        >>> m = flopy.modflow.Modflow()
        >>> lak = flopy.modflow.ModflowStr.load('test.lak', m)

        """

        if model.verbose:
            sys.stdout.write('loading lak package file...\n')

        if not hasattr(f, 'read'):
            filename = f
            if sys.version_info[0] == 2:
                f = open(filename, 'r')
            elif sys.version_info[0] == 3:
                f = open(filename, 'r', errors='replace')

        # dataset 0 -- header
        while True:
            line = f.readline()
            if line[0] != '#':
                break

        options = []
        tabdata = False
        if 'TABLEINPUT' in line.upper():
            if model.verbose:
                print("   reading lak dataset 1a")
            options.append('TABLEINPUT')
            tabdata = True
            line = f.readline()

        # read dataset 1b
        if model.verbose:
            print("   reading lak dataset 1b")
        t = line.strip().split()
        nlakes = int(t[0])
        ipakcb = 0
        try:
            ipakcb = int(t[1])
        except:
            pass

        # read dataset 2
        line = f.readline().rstrip()
        if model.array_free_format:
            t = line.split()
        else:
            t = read_fixed_var(line, ncol=4)
        theta = float(t[0])
        nssitr, sscncr = 0, 0.
        if theta < 0:
            try:
                nssitr = int(t[1])
            except:
                pass
            try:
                sscncr = float(t[2])
            except:
                pass
        surfdep = 0.
        if theta < 0.:
            surfdep = float(t[3])

        if nper is None:
            nrow, ncol, nlay, nper = model.get_nrow_ncol_nlay_nper()

        if model.verbose:
            print("   reading lak dataset 3")
        stages = []
        stage_range = []
        if tabdata:
            tab_units = []
        else:
            tab_units = None
        for lake in range(nlakes):
            line = f.readline().rstrip()
            if model.array_free_format:
                t = line.split()
            else:
                t = read_fixed_var(line, ipos=[10, 10, 10, 5])
            stages.append(t[0])
            ipos = 1
            if model.dis.steady[0]:
                stage_range.append((float(t[ipos]), float(t[ipos + 1])))
                ipos += 2
            if tabdata:
                iu = int(t[ipos])
                tab_units.append(iu)

        lake_loc = {}
        lake_lknc = {}
        sill_data = {}
        flux_data = {}
        for iper in range(nper):
            if model.verbose:
                print("   reading lak dataset 4 - " +
                      "for stress period {}".format(iper + 1))
            line = f.readline().rstrip()
            if model.array_free_format:
                t = line.split()
            else:
                t = read_fixed_var(line, ncol=3)
            itmp, itmp1, lwrt = int(t[0]), int(t[1]), int(t[2])

            if itmp > 0:
                if model.verbose:
                    print("   reading lak dataset 5 - " +
                          "for stress period {}".format(iper + 1))
                name = 'LKARR_StressPeriod_{}'.format(iper)
                lakarr = Util3d.load(f, model, (nlay, nrow, ncol), np.int,
                                     name, ext_unit_dict)
                if model.verbose:
                    print("   reading lak dataset 6 - " +
                          "for stress period {}".format(iper + 1))
                name = 'BDLKNC_StressPeriod_{}'.format(iper)
                bdlknc = Util3d.load(f, model, (nlay, nrow, ncol), np.float32,
                                     name, ext_unit_dict)

                lake_loc[iper] = lakarr
                lake_lknc[iper] = bdlknc

                if model.verbose:
                    print("   reading lak dataset 7 - " +
                          "for stress period {}".format(iper + 1))
                line = f.readline().rstrip()
                t = line.split()
                nslms = int(t[0])
                ds8 = []
                if nslms > 0:
                    if model.verbose:
                        print("   reading lak dataset 8 - " +
                              "for stress period {}".format(iper + 1))
                    for i in range(nslms):
                        line = f.readline().rstrip()
                        if model.array_free_format:
                            t = line.split()
                        else:
                            ic = int(line[0:5])
                            t = read_fixed_var(line, ncol=ic + 1, length=5)
                        ic = int(t[0])
                        ds8a = [ic]
                        for j in range(1, ic + 1):
                            ds8a.append(int(t[j]))
                        line = f.readline().rstrip()
                        if model.array_free_format:
                            t = line.split()
                        else:
                            t = read_fixed_var(line, ncol=ic - 1)
                        silvt = []
                        for j in range(ic - 1):
                            silvt.append(float(t[j]))
                        ds8.append((ds8a, silvt))
                    sill_data[iper] = ds8
            if itmp1 >= 0:
                if model.verbose:
                    print("   reading lak dataset 9 - " +
                          "for stress period {}".format(iper + 1))
                ds9 = {}
                for n in range(nlakes):
                    line = f.readline().rstrip()
                    if model.array_free_format:
                        t = line.split()
                    else:
                        t = read_fixed_var(line, ncol=6)
                    tds = []
                    tds.append(float(t[0]))
                    tds.append(float(t[1]))
                    tds.append(float(t[2]))
                    tds.append(float(t[3]))
                    if model.dis.steady[iper]:
                        if iper == 0:
                            tds.append(stage_range[n][0])
                            tds.append(stage_range[n][1])
                        else:
                            tds.append(float(t[4]))
                            tds.append(float(t[5]))
                    else:
                        tds.append(0.)
                        tds.append(0.)
                    ds9[n] = tds
                flux_data[iper] = ds9

        # convert lake data to Transient3d objects
        lake_loc = Transient3d(model, (nlay, nrow, ncol), np.int,
                               lake_loc, name='lakarr_')
        lake_lknc = Transient3d(model, (nlay, nrow, ncol), np.float32,
                                lake_lknc, name='bdlknc_')

        # determine specified unit number
        n = 2
        if tab_units is not None:
            n += nlakes
        unitnumber = None
        filenames = [None for x in range(n)]
        if ext_unit_dict is not None:
            unitnumber, filenames[0] = \
                model.get_ext_dict_attr(ext_unit_dict,
                                        filetype=ModflowLak.ftype())
            if ipakcb > 0:
                iu, filenames[1] = \
                    model.get_ext_dict_attr(ext_unit_dict, unit=ipakcb)
                model.add_pop_key_list(ipakcb)

            ipos = 2
            if tab_units is not None:
                for i in range(len(tab_units)):
                    iu, filenames[ipos] = \
                        model.get_ext_dict_attr(ext_unit_dict,
                                                unit=tab_units[i])
                    ipos += 1

        lakpak = ModflowLak(model, options=options, nlakes=nlakes,
                            ipakcb=ipakcb, theta=theta, nssitr=nssitr,
                            surfdep=surfdep, sscncr=sscncr, stages=stages,
                            stage_range=stage_range, tab_units=tab_units,
                            lakarr=lake_loc, bdlknc=lake_lknc,
                            sill_data=sill_data, flux_data=flux_data,
                            unitnumber=unitnumber, filenames=filenames)
        return lakpak

    @staticmethod
    def ftype():
        return 'LAK'

    @staticmethod
    def defaultunit():
        return 119
