from common.abstractdevices.script_scanner.scan_methods import experiment
from excitation_729 import excitation_729
from resonator.scripts.scriptLibrary.common_methods_729 import common_methods_729 as cm
from resonator.scripts.scriptLibrary import dvParameters
import time
import labrad
from labrad.units import WithUnit
import numpy as np
from common.okfpgaservers.pulser.pulse_sequences.plot_sequence import SequencePlotter

class spectrum(experiment):
    
    name = 'Spectrum729'
    required_parameters = [
                           ('Spectrum','custom'),
                           ('Spectrum','normal'),
                           ('Spectrum','fine'),
                           ('Spectrum','ultimate'),
                           ('Spectrum','opticalpumping'),
                           ('Spectrum','carrier'),
                           ('Spectrum', 'temperature'),
                           
                           ('Spectrum','line_selection'),
                           ('Spectrum','manual_amplitude_729'),
                           ('Spectrum','manual_excitation_time'),
                           ('Spectrum','manual_scan'),
                           ('Spectrum','scan_selection'),
                           ('Spectrum','sensitivity_selection'),
                           ('Spectrum','sideband_selection'),

                           ('TrapFrequencies','axial_frequency'),
                           ('TrapFrequencies','radial_frequency_1'),
                           ('TrapFrequencies','radial_frequency_2'),
                           ('TrapFrequencies','rf_drive_frequency'),
                           ]
    
    optional_parmeters = [
                          ('Spectrum', 'window_name'),
                          ('Spectrum', 'dataset_name_append'),
                          ('Spectrum', 'save_directory')
                          ]
    required_parameters.extend(excitation_729.required_parameters)
    #removing parameters we'll be overwriting, and they do not need to be loaded
    required_parameters.remove(('Excitation_729','rabi_excitation_amplitude'))
    required_parameters.remove(('Excitation_729','rabi_excitation_duration'))
    required_parameters.remove(('Excitation_729','rabi_excitation_frequency'))
    
    
    def initialize(self, cxn, context, ident):
        self.ident = ident
        self.excite = self.make_experiment(excitation_729)
        self.excite.initialize(cxn, context, ident)
        self.scan = []
        self.amplitude = None
        self.duration = None
        self.cxnlab = labrad.connect('192.168.169.49') #connection to labwide network
        self.drift_tracker = cxn.sd_tracker
        self.dv = cxn.data_vault
        self.pulser = cxn.pulser
        self.fitter = None
        try:
            self.fitter = cxn.fitter
        except:
            print "No data analyzer"
        self.spectrum_save_context = cxn.context()
    
    def setup_sequence_parameters(self):
        sp = self.parameters.Spectrum
        if sp.scan_selection == 'manual':
            minim,maxim,steps = sp.manual_scan
            duration = sp.manual_excitation_time
            amplitude = sp.manual_amplitude_729
        elif sp.scan_selection == 'auto':
            center_frequency = cm.frequency_from_line_selection(sp.scan_selection, None , sp.line_selection, self.drift_tracker)
            center_frequency = cm.add_sidebands(center_frequency, sp.sideband_selection, self.parameters.TrapFrequencies)
            span, resolution, duration, amplitude = sp[sp.sensitivity_selection]
            minim = center_frequency - span / 2.0
            maxim = center_frequency + span / 2.0
            steps = int(span / resolution )
        else:
            raise Exception("Incorrect Spectrum Scan Type")
        #making the scan
        self.parameters['Excitation_729.rabi_excitation_duration'] = duration
        self.parameters['Excitation_729.rabi_excitation_amplitude'] = amplitude
        minim = minim['MHz']; maxim = maxim['MHz']
        self.scan = np.linspace(minim,maxim, steps)
        self.scan = [WithUnit(pt, 'MHz') for pt in self.scan]

        
    def setup_data_vault(self):
        localtime = time.localtime()        
        # check if there's a specified save directory and dataset
        try:
            directory = self.parameters.get('Spectrum.save_directory')
            datasetNameAppend = self.parameters.get('Spectrum.dataset_name_append')
        except KeyError:
            dirappend = [ time.strftime("%Y%b%d",localtime) ,time.strftime("%H%M_%S", localtime)]
            directory = ['','Experiments']
            directory.extend([self.name])
            directory.extend(dirappend)
            datasetNameAppend = time.strftime("%Y%b%d_%H%M_%S",localtime)

        self.datasetName = 'Spectrum {}'.format(datasetNameAppend)        
        self.dv.cd(directory ,True, context = self.spectrum_save_context)
        self.dv.new(self.datasetName,[('Freq', 'MHz')],[('Excitation Probability','Arb','Arb')], context = self.spectrum_save_context)
        window_name = self.parameters.get('Spectrum.window_name', ['Spectrum'])
        self.dv.add_parameter('Window', window_name, context = self.spectrum_save_context)
        self.dv.add_parameter('plotLive', True, context = self.spectrum_save_context)
        self.directory = directory
        
    def run(self, cxn, context):
        self.setup_data_vault()
        self.setup_sequence_parameters()
        self.pulser.switch_auto('397mod')
        self.pulser.switch_auto('parametric_modulation')
        for i,freq in enumerate(self.scan):
            should_stop = self.pause_or_stop()
            if should_stop: break
            self.parameters['Excitation_729.rabi_excitation_frequency'] = freq
            self.excite.set_parameters(self.parameters)
            excitation = self.excite.run(cxn, context)
            self.dv.add((freq, excitation), context = self.spectrum_save_context)
            self.update_progress(i)
        if self.fitter is not None:

            dir = (self.directory, 1)
            print dir
            self.fitter.load_data(dir)
            self.fitter.fit('Lorentzian', True)
            
            accepted = self.fitter.wait_for_acceptance()
            
            if accepted:
                center = WithUnit(self.fitter.get_parameter('Center'), 'MHz')
                fwhm = self.fitter.get_parameter('FWHM')
                height = self.fitter.get_parameter('Height')
                print center
                print fwhm
                print height
                return (center, fwhm, height)
            else:
                print 'fit rejected!'
            
        
        #dds = self.cxn.pulser.human_readable_dds()
        #ttl = self.cxn.pulser.human_readable_ttl()
        #channels = self.cxn.pulser.get_channels().asarray
        #sp = SequencePlotter(ttl.asarray, dds.aslist, channels)
        #sp.makePlot()
    
    def fit_lorentzian(self, timeout):
        #for lorentzian format is FWHM, center, height, offset
        scan = np.array([pt['MHz'] for pt in self.scan])
        
        fwhm_guess = (scan.max() - scan.min()) / 10.0
        center_guess = np.average(scan)
        self.dv.add_parameter('Fit', ['0', 'Lorentzian', '[{0}, {1}, {2}, {3}]'
                                      .format(fwhm_guess, center_guess, 0.5, 0.0)], context = self.spectrum_save_context)
        submitted = self.cxn.data_vault.wait_for_parameter('Accept-0', timeout, context = self.spectrum_save_context)
        if submitted:
            return self.cxn.data_vault.get_parameter('Solutions-0-Lorentzian', context = self.spectrum_save_context)
        else:
            return None

    def finalize(self, cxn, context):
        self.save_parameters(self.dv, cxn, self.cxnlab, self.spectrum_save_context)

    def update_progress(self, iteration):
        progress = self.min_progress + (self.max_progress - self.min_progress) * float(iteration + 1.0) / len(self.scan)
        self.sc.script_set_progress(self.ident,  progress)

    def save_parameters(self, dv, cxn, cxnlab, context):
        measuredDict = dvParameters.measureParameters(cxn, cxnlab)
        dvParameters.saveParameters(dv, measuredDict, context)
        dvParameters.saveParameters(dv, dict(self.parameters), context)   

if __name__ == '__main__':
    cxn = labrad.connect()
    scanner = cxn.scriptscanner
    exprt = spectrum(cxn = cxn)
    ident = scanner.register_external_launch(exprt.name)
    exprt.execute(ident)
