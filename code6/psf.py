'''
A base point spread function interface
'''
import numpy as np
from numpy import floor
from numpy import power as npow
from numpy.fft import fft2, fftshift, ifftshift, ifft2

from matplotlib import pyplot as plt

from code6.conf import config
from code6.fttools import pad2d, forward_ft_unit
from code6.coordinates import uniform_cart_to_polar, resample_2d_complex
from code6.util import pupil_sample_to_psf_sample, correct_gamma, share_fig_ax, fold_array

class PSF(object):
    '''Point Spread Function representations

    Properties:
        slice_x: 1D slice through center of PSF along X axis.  Returns (x,y) data

        slice_y: 1D slice through cente rof PSF along y axis.  Returns (x,y) data

    Instance Methods:
        encircled_energy: Computes the encircled energy along the specified
            azimuth. If azimuth is none, returns the azimuthal average.
            Returned value is the average of both the negative and positive
            sides of the PSF along the specified azimuth.

        plot2d: Makes a 2D plot of the PSF.  Returns (fig, axis)

        plot_slice_xy: Makes a 1D plot with x and y slices through the center
            of the PSF.  Returns (fig, axis).

        plot_encircled_energy: Makes a 1D plot of the encircled energy at the
            specified azimuth.  Returns (fig, axis)

        conv: convolves this PSF with another.  Returns a new PSF object that is
            sampled at the same points as this PSF.

    Private Instance Methods:
        _renorm: renormalizes the PSF to unit peak intensity

    Static Methods:
        from_pupil: given a pupil and a focal length, returns a PSF.

    Notes:
        Subclasses must implement an analyic_ft method with signature
            a_ft(unit_x, unit_y)

    '''
    def __init__(self, data, samples, sample_spacing):
        '''Creates a PSF object

        Args:
            data (numpy.ndarray): intensity data for the PSF
            samples (int): number of samples along each axis of the PSF.
                for a 256x256 PSF, samples=256
            sample_spacing (float): center-to-center spacing of samples,
                expressed in microns.

        Returns:
            PSF.  A new PSF instance.

        '''
        self.data = data
        self.samples = samples
        self.sample_spacing = sample_spacing
        self.center = int(floor(samples/2))

        # compute ordinate axis
        ext = self.sample_spacing * samples / 2
        self.unit = np.linspace(-ext, ext-sample_spacing, samples, dtype=config.precision)

    # quick-access slices ------------------------------------------------------

    @property
    def slice_x(self):
        '''Retrieves a slice through the x axis of the PSF
        '''
        return self.unit, self.data[self.center, :]

    @property
    def slice_y(self):
        '''Retrieves a slices through the y axis of the PSF
        '''
        return self.unit, self.data[:, self.center]


    def encircled_energy(self, azimuth=None):
        '''returns the encircled energy at the requested azumith.  If azimuth is
            None, returns the azimuthal average

        Args:
            azimuth (float): azimuth to retrieve data along, in degrees.

        Returns:
            np.ndarray, np.ndarray.  Unit, encircled energy.

        '''
        rho, phi, interp_dat = uniform_cart_to_polar(self.unit, self.unit, self.data)
        avg_fold = fold_array(interp_dat)

        if azimuth is None:
            # take average of all azimuths as input data
            dat = np.average(avg_fold, axis=0, dtype=config.precision)
        else:
            index = np.searchsorted(phi, np.radians(azimuth, dtype=config.precision))
            dat = avg_fold[index, :]

        enc_eng = np.cumsum(dat, dtype=config.precision)
        enc_eng /= enc_eng[-1]
        return self.unit[self.center:], enc_eng

    # quick-access slices ------------------------------------------------------

    # plotting -----------------------------------------------------------------

    def plot2d(self, log=False, axlim=25, interp_method='bicubic',
               pix_grid=None, fig=None, ax=None):
        '''Creates a 2D plot of the PSF

        Args:
            log (bool): if true, plot in log scale.  If false, plot in linear scale
            axlim (float): limits of axis, symmetric.
                xlim=(-axlim,axlim), ylim=(-axlim, axlim).
            interp_method (string): method used to interpolate the image between
                samples of the PSF
            pix_grid (float): if not None, overlays gridlines with spacing equal
                to pix_grid.  Intended to show the collection into camera pixels
                while still in the oversampled domain.
            fig (pyplot.figure): figure to plot in
            ax (pyplot.axis): axis to plot in

        Returns:
            pyplot.fig, pyplot.axis.  Figure and axis containing the plot

        '''
        if log:
            fcn = 20 * np.log10(1e-100 + self.data)
            label_str = 'Normalized Intensity [dB]'
            lims = (-100, 0) # show first 100dB -- range from (1e-6, 1) in linear scale
        else:
            fcn = correct_gamma(self.data)
            label_str = 'Normalized Intensity [a.u.]'
            lims = (0, 1)

        left, right = self.unit[0], self.unit[-1]

        fig, ax = share_fig_ax(fig, ax)

        im = ax.imshow(fcn,
                       extent=[left, right, left, right],
                       cmap='Greys_r',
                       interpolation=interp_method,
                       clim=lims)
        fig.colorbar(im, label=label_str, ax=ax, fraction=0.046)
        ax.set(xlabel=r'Image Plane X [$\mu m$]',
               ylabel=r'Image Plane Y [$\mu m$]',
               xlim=(-axlim, axlim),
               ylim=(-axlim, axlim))

        if pix_grid is not None:
            # if pixel grid is desired, add it
            mult = np.floor(axlim / pix_grid)
            gmin, gmax = -mult * pix_grid, mult*pix_grid
            pts = np.arange(gmin, gmax, pix_grid)
            ax.set_yticks(pts, minor=True)
            ax.set_xticks(pts, minor=True)
            ax.yaxis.grid(True, which='minor')
            ax.xaxis.grid(True, which='minor')
        
        return fig, ax

    def plot_slice_xy(self, log=False, axlim=20, fig=None, ax=None):
        '''Makes a 1D plot of X and Y slices through the PSF

        Args:
            log (bool): if true, plot in log scale.  if false, plot in linear scale
            axlim (float): limits of axis, Will plot [-axlim, axlim]
            fig (pyplot.figure): figure to plot in
            ax (pyplot.axis): axis to plot in

        Returns:
            pyplot.fig, pyplot.axis.  Figure and axis containing the plot

        '''
        u, x = self.slice_x
        _, y = self.slice_y
        if log:
            fcn_x = 20 * np.log10(1e-100 + x)
            fcn_y = 20 * np.log10(1e-100 + y)
            label_str = 'Normalized Intensity [dB]'
            lims = (-120, 0)
        else:
            fcn_x = x
            fcn_y = y
            label_str = 'Normalized Intensity [a.u.]'
            lims = (0, 1)

        fig, ax = share_fig_ax(fig, ax)

        ax.plot(u, fcn_x, label='Slice X', lw=3)
        ax.plot(u, fcn_y, label='Slice Y', lw=3)
        ax.set(xlabel=r'Image Plane X [$\mu m$]',
               ylabel=label_str,
               xlim=(-axlim, axlim),
               ylim=lims)
        plt.legend(loc='upper right')
        return fig, ax

    def plot_encircled_energy(self, azimuth=None, axlim=20, fig=None, ax=None):
        '''Makes a 1D plot of the encircled energy at the given azimuth

        Args:
            azimuth: azimuth to plot at, in degrees.
            axlim (float): limits of axis, will plot [0, axlim]
            fig (pyplot.figure): figure to plot in
            ax (pyplot.axis): axis to plot in

        Returns:
            pyplot.fig, pyplot.axis.  Figure and axis containing the plot

        '''
        unit, data = self.encircled_energy(azimuth)

        fig, ax = share_fig_ax(fig, ax)
        ax.plot(unit, data, lw=3)
        ax.set(xlabel=r'Image Plane Distance [$\mu m$]',
               ylabel=r'Encircled Energy [Rel 1.0]',
               xlim=(0, axlim))
        return fig, ax

    # plotting -----------------------------------------------------------------

    # helpers ------------------------------------------------------------------

    def conv(self, psf2):
        '''Convolves this PSF with another

        Args:
            psf2 (code6.PSF): PSf to convolve with this one

        Returns:
            PSF.  A new PSF, that is the convolution of these two PSFs.

        Notes:
            output PSF has equal sampling to whichever PSF has a lower nyquist
                frequency.

        '''
        if issubclass(psf2.__class__, PSF):
            # subclasses have analytic fourier transforms and we can exploit this for high speed,
            # aliasing-free convolution
            psf_ft = fft2(self.data)
            psf_unit = forward_ft_unit(self.sample_spacing, self.samples)
            psf2_ft = fftshift(psf2.analytic_ft(psf_unit, psf_unit))
            psf3 = PSF(data=np.absolute(ifft2(psf_ft * psf2_ft), dtype=config.precision),
                       samples=self.samples,
                       sample_spacing=self.sample_spacing)
            return psf3._renorm()
        return convpsf(self, psf2)

    def _renorm(self):
        '''Renormalizes the PSF to unit peak intensity
        '''
        self.data /= self.data.max()
        return self

    # helpers ------------------------------------------------------------------

    @staticmethod
    def from_pupil(pupil, efl, padding=1):
        '''Uses scalar diffraction propogation to generate a PSF from a pupil

        Args:
            pupil (code6.Pupil): Pupil, with OPD data and wavefunction.
            efl (float): effective focal length of the optical system
            padding (number): number of pupil widths to pad each side of the
                pupil with during computation

        Returns:
            PSF.  A new PSF instance.

        '''
        # padded pupil contains 1 pupil width on each side for a width of 3
        psf_samples = (pupil.samples * padding) * 2 + pupil.samples
        sample_spacing = pupil_sample_to_psf_sample(pupil_sample=pupil.sample_spacing * 1000,
                                                    num_samples=psf_samples,
                                                    wavelength=pupil.wavelength,
                                                    efl=efl)
        padded_wavefront = pad2d(pupil.fcn, padding)
        impulse_response = ifftshift(fft2(fftshift(padded_wavefront)))
        psf = npow(np.absolute(impulse_response, dtype=config.precision), 2)
        return PSF(psf / np.max(psf), psf_samples, sample_spacing)


def convpsf(psf1, psf2):
    '''Convolves two PSFs.

    Args:
        psf1 (code6.PSF): first PSF
        psf2 (code6.PSF): second PSF

    Returns:
        PSF.  A new PSF that is the convolution of psf1 and psf2.

    Notes:
        The PSF with the lower nyquist frequency defines the sampling of the
            output.  The PSF with a higher nyquist will be truncated in
            the frequency domain (without aliasing) and projected onto the
            sampling grid of the PSF with a lower nyquist.

    '''
    if psf2.samples == psf1.samples and psf2.sample_spacing == psf1.sample_spacing:
        # no need to interpolate, use FFTs to convolve
        psf3 = PSF(data=np.absolute(ifftshift(ifft2(fft2(psf1.data) * fft2(psf2.data))), dtype=config.precision),
                   samples=psf1.samples,
                   sample_spacing=psf1.sample_spacing)
        return psf3._renorm()
    else:
        # need to interpolate, suppress all frequency content above nyquist for the less sampled psf
        if psf1.sample_spacing > psf2.sample_spacing:
            # psf1 has the lower nyquist, resample psf2 in the fourier domain to match psf1
            return _unequal_spacing_conv_core(psf1, psf2)
        else:
            # psf2 has lower nyquist, resample psf1 in the fourier domain to match psf2
            return _unequal_spacing_conv_core(psf2, psf1)

def _unequal_spacing_conv_core(psf1, psf2):
    '''Interpolates psf2 before using fft-based convolution

    Args:
        psf1 (code6.PSF): PSF.  This one defines the sampling of the output.
        psf2 (code6.PSF): PSF.  This one will have its frequency response
            truncated.

    Returns:
        PSF.  A new PSF that is the convolution of psf1 and psf2.

    '''
    ft1 = fft2(psf1.data)
    unit1 = forward_ft_unit(psf1.sample_spacing, psf1.samples)
    ft2 = fft2(psf2.data)
    unit2 = forward_ft_unit(psf2.sample_spacing, psf2.samples)
    ft3 = resample_2d_complex(ft2, (unit2, unit2), (unit1, unit1[::-1]))
    psf3 = PSF(data=np.absolute(ifftshift(ifft2(ft1 * ft3)), dtype=config.precision),
               samples=psf1.samples,
               sample_spacing=psf2.sample_spacing)
    return psf3._renorm()
