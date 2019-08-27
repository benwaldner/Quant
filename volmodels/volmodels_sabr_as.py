#!/usr/bin/env python
# coding: utf-8

import numpy as np
import abc
from scipy.special import erfi
from volmodels import Vol_model, ONE_BP

# Modified SABR with repulsive local vol at zero.
# In regular SABR, beta controls the backbone shape. A repulsive local vol floor creates 
# an increasing backbone for lower rates, which can be a stylized fact of the option 
# market in low rates environment near a perceived rates floor.
class SABR_AS_base_model(Vol_model):
    """Generic class for SABR_tanh model
    dX_t = s_t*C(X_t)*dW_t
    ds_t = vov*s_t*dB_t
    d<W,B>_t = rho*dt
    C(x) = exp(-c*log(y/K_max)^2)
    """
    def __init__(self, 
                 K_max: float=1.0,
                 c: float=1.0, 
                 vov: float=1.0,
                 rho: float=0.0,
                 sigma_0=None,
                 f=None,
                 T_expiry: float=1.0,
                 vol_type=None,
                 logmoneyness_lo=None,
                 logmoneyness_hi=None,
                 K_lo=None,
                 K_hi=None,
                 strike_type: str='logmoneyness',
                 n_strikes: int=50,
                ) -> None:
        """Implementation of SABR implied vol and approximated price formula.
        K_max, c, vov and rho are marked.
        """
        super().__init__(f=f, 
                         T_expiry=T_expiry,
                         vol_type=vol_type,
                         logmoneyness_lo=logmoneyness_lo,
                         logmoneyness_hi=logmoneyness_hi,
                         K_lo=K_lo,
                         K_hi=K_hi,
                         strike_type=strike_type,
                         n_strikes=n_strikes
                        )
        self._c = c
        self._K_max = K_max
        self._vov = vov
        self._rho = rho
        self._sigma_0 = sigma_0

    @property
    def c(self):
        return self._c
    @c.setter
    def c(self, new_c):
        self._c = new_c
    
    @property
    def K_max(self):
        return self._K_max
    @K_max.setter
    def K_max(self, new_K_max):
        self._K_max = new_K_max
        
    @property
    def rho(self):
        return self._rho
    @rho.setter
    def rho(self, new_rho):
        self._rho = new_rho
     
    @property
    def vov(self):
        return self._vov
    @vov.setter
    def vov(self, new_vov):
        self._vov = new_vov
    
    @property
    def sigma_0(self):
        return self._sigma_0
    @sigma_0.setter
    def sigma_0(self, new_sigma_0):
        self._sigma_0 = new_sigma_0

    def __str__(self):
        return r'c={:.3%}, K_max={:.2f}bps, vov={:.0%}, $\rho$={:.0%}, ATM={:.2%}, f={:.2%}, $\sigma_0$={:.2%}'        .format(self.c, self.K_max/ONE_BP, self.vov, self.rho, self.ATM, self.f, self.sigma_0)
    
    def local_vol_inv_int(self, x):
        """Closed form for the primitive of 1/(exp(-c*log(x/K_max)^2))
        """
        return (np.exp(-1/(4*self.c))*self.K_max*np.sqrt(np.pi)                *erfi((1+2*self.c*np.log(x/self.K_max))/(2*np.sqrt(self.c))))/(2*np.sqrt(self.c))
    
    @abc.abstractmethod
    def smile_func(self, K):
        pass

class SABR_AS_LN(SABR_AS_base_model):
    """SABR_AS model using lognormal implied vol quoting
    """
    def __init__(self, 
                 K_max: float=1.0,
                 c: float=1.0, 
                 vov: float=1.0,
                 rho: float=0.0,
                 sigma_0=None,
                 f=None,
                 T_expiry: float=1.0,
                 logmoneyness_lo=None,
                 logmoneyness_hi=None,
                 K_lo=None,
                 K_hi=None,
                 strike_type: str='logmoneyness',
                 n_strikes: int=50,
                ) -> None:
        super().__init__(K_max=K_max,
                         c=c,
                         vov=vov,
                         rho=rho,
                         sigma_0=sigma_0,
                         f=f,
                         T_expiry=T_expiry,
                         vol_type='LN',
                         logmoneyness_lo=logmoneyness_lo,
                         logmoneyness_hi=logmoneyness_hi,
                         K_lo=K_lo,
                         K_hi=K_hi,
                         strike_type=strike_type,
                         n_strikes=n_strikes
                        )

    @property
    def model_name(self):
        return 'SABR_AS_LN'
    
    @property
    def ATM_LN(self):
        f_adj = self.f/self.K_max
        C_f_adj = np.exp(-self.c*np.log(f_adj)**2)    
        gamma_1 = -(2*self.c*np.log(f_adj))/self.f
        gamma_2 = (2*self.c*(-1+np.log(f_adj)+2*self.c*np.log(f_adj)**2))/(self.f**2)
        
        return self.sigma_0/self.f*C_f_adj    *(1      +((2*gamma_2-gamma_1**2+1/(self.f**2))/24*self.sigma_0**2*C_f_adj**2       +0.25*self.rho*self.vov*self.sigma_0*gamma_1*C_f_adj       +(2-3*self.rho**2)/24*self.vov**2)      *self.T_expiry)

    @property
    def ATM(self):
        return self.ATM_LN
    
    def smile_func(self, K):
        """Hagan lognormal smile approximation around ATM as written in the
        original 'Managing Smile Risk' paper using generic local vol (A.65)
        K: strike
        """
        if np.abs(K-self.f)<ONE_BP/100:
            return self.ATM
        else:
            log_moneyness = np.log(self.f/K)
            f_avg = np.sqrt(self.f*K)
            f_avg_adj = f_avg/self.K_max
            C_f_avg_adj = np.exp(-self.c*np.log(f_avg_adj)**2)
            
            gamma_1 = -(2*self.c*np.log(f_avg_adj))/f_avg
            gamma_2 = (2*self.c*(-1+np.log(f_avg_adj)+2*self.c*np.log(f_avg_adj)**2))/(f_avg**2)
            
            denom = self.local_vol_inv_int(self.f)-self.local_vol_inv_int(K)
            zeta = self.vov/self.sigma_0*(self.f-K)/C_f_avg_adj
            q_zeta = 1-2*self.rho*zeta+zeta**2
            x_zeta = np.log((np.sqrt(q_zeta)-self.rho+zeta)/(1-self.rho))
            return self.sigma_0*log_moneyness/denom*zeta/x_zeta        *(1          +((2*gamma_2-gamma_1**2+1/(f_avg**2))/24*self.sigma_0**2*C_f_avg_adj**2           +0.25*self.rho*self.vov*self.sigma_0*gamma_1*C_f_avg_adj           +(2-3*self.rho**2)/24*self.vov**2)          *self.T_expiry)

class SABR_AS_N(SABR_AS_base_model):
    """SABR_AS model using lognormal implied vol quoting
    """
    def __init__(self, 
                 K_max: float=1.0,
                 c: float=1.0, 
                 vov: float=1.0,
                 rho: float=0.0,
                 sigma_0=None,
                 f=None,
                 T_expiry: float=1.0,
                 logmoneyness_lo=None,
                 logmoneyness_hi=None,
                 K_lo=None,
                 K_hi=None,
                 strike_type: str='logmoneyness',
                 n_strikes: int=50,
                ) -> None:
        super().__init__(K_max=K_max, 
                         c=c,
                         vov=vov,
                         rho=rho,
                         sigma_0=sigma_0,
                         f=f,
                         T_expiry=T_expiry,
                         vol_type='N',
                         logmoneyness_lo=logmoneyness_lo,
                         logmoneyness_hi=logmoneyness_hi,
                         K_lo=K_lo,
                         K_hi=K_hi,
                         strike_type=strike_type,
                         n_strikes=n_strikes
                        )
    
    @property
    def model_name(self):
        return 'SABR_AS_N'
    
    @property
    def ATM_N(self):
        f_adj = self.f/self.K_max
        C_f_adj = np.exp(-self.c*np.log(f_adj)**2)    
        gamma_1 = -(2*self.c*np.log(f_adj))/self.f
        gamma_2 = (2*self.c*(-1+np.log(f_adj)+2*self.c*np.log(f_adj)**2))/(self.f**2)
            
        return self.sigma_0*C_f_adj    *(1      +((2*gamma_2-gamma_1**2)/24*self.sigma_0**2*C_f_adj**2       +0.25*self.rho*self.vov*self.sigma_0*gamma_1*C_f_adj       +(2-3*self.rho**2)/24*self.vov**2)      *self.T_expiry)

    @property
    def ATM(self):
        return self.ATM_N
    
    def smile_func(self, K):
        """Hagan lognormal smile approximation around ATM as written in the
        original 'Managing Smile Risk' paper using generic local vol (A.65)
        K: strike
        """
        if np.abs(K-self.f)<ONE_BP/100:
            return self.ATM
        else:
            f_avg = np.sqrt(self.f*K)
            f_avg_adj = f_avg/self.K_max
            C_f_avg_adj = np.exp(-self.c*np.log(f_avg_adj)**2)
            
            gamma_1 = -(2*self.c*np.log(f_avg_adj))/f_avg
            gamma_2 = (2*self.c*(-1+np.log(f_avg_adj)+2*self.c*np.log(f_avg_adj)**2))/(f_avg**2)
            
            denom = self.local_vol_inv_int(self.f)-self.local_vol_inv_int(K)
            zeta = self.vov/self.sigma_0*(self.f-K)/C_f_avg_adj
            q_zeta = 1-2*self.rho*zeta+zeta**2
            x_zeta = np.log((np.sqrt(q_zeta)-self.rho+zeta)/(1-self.rho))
            return self.sigma_0*(self.f-K)/denom*zeta/x_zeta        *(1          +((2*gamma_2-gamma_1**2)/24*self.sigma_0**2*C_f_avg_adj**2           +0.25*self.rho*self.vov*self.sigma_0*gamma_1*C_f_avg_adj           +(2-3*self.rho**2)/24*self.vov**2)          *self.T_expiry)